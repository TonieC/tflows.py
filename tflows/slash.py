"""Slash-command support for tflows scripts.

Python API::

    bot.command("greet", 'reply Hello $arg(0)!', slash=True,
                slash_params=["name"])
    bot.slashcommand("roll", 'send Rolled $arg(0)', params=["sides: int"])

    # ... then, once the bot is ready:
    await bot.sync_commands()

Slash parameters are mapped positionally into the existing scripting
system: values are joined (in order) into ``$args`` so ``$args``,
``$arg(n)`` and ``$argcount`` keep working unchanged. Named access via
``$arg(name)`` also works (see :mod:`tflows.function.args`).

Prefix commands are untouched: enabling ``slash=True`` adds a slash
variant, it never removes the prefix command.
"""

import logging
import re

logger = logging.getLogger("tflows.slash")

_PARAM_TYPES = {"str": str, "int": int, "float": float, "bool": bool}

_DEFAULTS = {"str": "", "int": 0, "float": 0.0, "bool": False}


def _sanitize_param_name(name: str) -> str:
    name = (name or "").strip().lower().replace(" ", "_").replace("-", "_")
    name = re.sub(r"[^a-z0-9_]", "", name)
    if not name:
        raise ValueError("empty slash parameter name")
    if name[0].isdigit():
        name = "p_" + name
    return name[:32]


def parse_slash_params(params) -> list:
    """Normalize user ``params`` into ``[(name, type)]``.

    Accepts ``["name", "count: int"]``, ``[("count", int)]``,
    ``{"count": int}`` or ``None`` (no parameters).
    """
    if params is None:
        return []
    if isinstance(params, dict):
        items = list(params.items())
    else:
        items = list(params)
    normalized = []
    for item in items:
        if isinstance(item, str):
            if ":" in item:
                name, _, type_name = item.partition(":")
                type_name = type_name.strip().lower()
                if type_name not in _PARAM_TYPES:
                    raise ValueError(
                        f"unknown slash param type {type_name!r} in {item!r}; "
                        "expected str, int, float or bool"
                    )
            else:
                name, type_name = item, "str"
            py_type = _PARAM_TYPES[type_name]
            normalized.append((_sanitize_param_name(name), py_type))
        elif isinstance(item, (tuple, list)) and len(item) == 2:
            name, py_type = item
            if isinstance(py_type, str):
                py_type = _PARAM_TYPES.get(py_type.strip().lower(), str)
            if py_type not in (str, int, float, bool):
                raise ValueError(f"unsupported slash param type: {py_type!r}")
            normalized.append((_sanitize_param_name(str(name)), py_type))
        else:
            raise ValueError(
                "slash params must be names ('name'), 'name: type' strings, "
                f"(name, type) tuples or a dict; got {item!r}"
            )
    if len({n for n, _ in normalized}) != len(normalized):
        raise ValueError(f"duplicate slash parameter names: {params!r}")
    if len(normalized) > 25:
        raise ValueError("discord slash commands support at most 25 parameters")
    return normalized


class _InteractionState:
    """Minimal ``_state`` shim so engine code using ``ctx._state`` works."""

    def __init__(self, bot):
        self._bot = bot

    def _get_client(self):
        return self._bot


class _InteractionChannel:
    """Routes ``send`` to the interaction response, then followups."""

    def __init__(self, interaction, bot):
        self._interaction = interaction
        self._bot = bot
        self._responded = False
        self.id = getattr(getattr(interaction, "channel", None), "id", 0)
        self.name = getattr(getattr(interaction, "channel", None), "name", "slash")
        self.mention = getattr(getattr(interaction, "channel", None), "mention", "#slash")
        self.sent = []

    async def send(self, content=None, **kwargs):
        self.sent.append((content, kwargs))
        interaction = self._interaction
        try:
            sender = (
                interaction.followup.send
                if self._responded
                else interaction.response.send_message
            )
            self._responded = True
            if content is None:
                await sender(**kwargs)
            else:
                await sender(content=str(content), **kwargs)
        except Exception:
            # Not connected to Discord (tests) or already handled: fall back
            # to the real channel when available.
            channel = getattr(self._bot, "get_channel", lambda _i: None)(self.id)
            if channel is not None and channel is not self:
                await channel.send(content, **kwargs)

    def permissions_for(self, _member):
        import discord

        return discord.Permissions.all()


class _InteractionMessage:
    """Message-like shim wrapping a slash interaction for FlowContext."""

    def __init__(self, interaction, bot, content: str):
        self._interaction = interaction
        self._bot = bot
        self.content = content
        self.author = interaction.user
        self.channel = _InteractionChannel(interaction, bot)
        self.guild = getattr(interaction, "guild", None)
        self.mentions = []
        self._state = _InteractionState(bot)
        try:
            from datetime import datetime, timezone

            self.created_at = datetime.now(timezone.utc)
        except Exception:
            self.created_at = None

    async def reply(self, content=None, **kwargs):
        await self.channel.send(content, **kwargs)

    async def add_reaction(self, _emoji):
        return None

    async def delete(self):
        return None


def build_slash_callback(bot, command_name: str, params: list):
    """Build the ``discord.app_commands`` callback running the script."""

    async def _callback(interaction, **values):
        from .context import FlowContext

        ordered = [values.get(name) for name, _ in params]
        # Drop trailing defaults so $argcount reflects provided arguments.
        while ordered and ordered[-1] in (None, ""):
            ordered.pop()
        args = " ".join("" if v is None else str(v) for v in ordered)
        named = {name: ("" if values.get(name) is None else str(values.get(name))) for name, _ in params}
        message = _InteractionMessage(interaction, bot, f"/{command_name} {args}".rstrip())
        ctx = FlowContext(
            message=message, bot=bot, command_name=command_name, args=args, kwargs=named
        )
        try:
            await bot.engine.run(ctx, bot.script_commands[command_name].code)
        except Exception:
            if getattr(bot, "log_errors", True):
                logger.exception("[tflow] Error running slash command %r", command_name)
            try:
                await message.channel.send("Something went wrong running that command.")
            except Exception:
                pass

    _callback.__name__ = f"tflow_slash_{command_name}"
    return _callback


def build_slash_command(bot, script_command, params: list):
    """Compile a :class:`ScriptCommand` into ``discord.app_commands.Command``."""
    import discord

    callback = build_slash_callback(bot, script_command.name, params)

    # app_commands derives parameters from the callback signature, so
    # generate one with explicit annotated parameters (defaults = optional).
    type_names = {str: "str", int: "int", float: "float", bool: "bool"}
    lines = ["async def _cb(interaction: discord.Interaction,"]
    for name, py_type in params:
        lines.append(f"    {name}: {type_names[py_type]} = { _DEFAULTS[type_names[py_type]]!r},")
    lines.append("):")
    lines.append("    return await _callback(interaction, **{")
    for name, _ in params:
        lines.append(f"        '{name}': {name},")
    lines.append("    })")
    namespace = {"discord": discord, "_callback": callback}
    exec("\n".join(lines), namespace)  # noqa: S102 - names are sanitized
    runner = namespace["_cb"]
    # Keep __name__ and __qualname__ in sync: app_commands uses qualname to
    # detect methods, and a mismatch is misread as a bound method.
    runner.__name__ = runner.__qualname__ = f"tflow_slash_{script_command.name}"

    description = (script_command.description or f"Run /{script_command.name}").strip()[:100]
    return discord.app_commands.Command(
        name=script_command.name.lower().replace(" ", "-"),
        description=description,
        callback=runner,
    )

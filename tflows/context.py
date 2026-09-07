"""Execution context passed through tflows scripts.

:class:`FlowContext` wraps the Discord message that triggered a script and
forwards every attribute needed by script functions (``channel``, ``author``,
``guild``, ``mentions``, ...) to the underlying message. This keeps the
scripting API identical whether the script is run from a raw
:class:`discord.Message` or from a :class:`FlowContext`.

Slash commands, scheduled tasks and event handlers build synthetic contexts
via :meth:`FlowContext.for_interaction`-style helpers so the same scripts run
unchanged outside prefix commands.
"""

from typing import Any

from .runtime import FlowValue, stringify


class FlowContext:
    """A lightweight context object available to every scripted function.

    Parameters
    ----------
    message:
        The :class:`discord.Message` that triggered the script (or a shim
        with the same surface for slash/scheduled/event runs).
    bot:
        The :class:`~tflows.FlowBot` instance executing the script.
    command_name:
        The script command name that was invoked (``None`` when run directly).
    args:
        Raw argument string that followed the command name.
    kwargs:
        Named arguments (slash-command parameters), also readable via
        ``$arg(name)``.
    extras:
        Event / interaction specific objects (``message``, ``emoji``,
        ``value``, ``interaction``, ...). Exposed as ``$name`` variables.
    """

    __slots__ = (
        "message",
        "bot",
        "command_name",
        "args",
        "kwargs",
        "locals",
        "extras",
        "pending_view",
        "pending_components",
        "pending_modal",
        "component_handlers",
        "ephemeral",
        "deferred",
        "interaction",
        "filename",
        "return_value",
    )

    def __init__(
        self,
        message,
        bot=None,
        command_name=None,
        args="",
        kwargs=None,
        extras=None,
        locals=None,
        interaction=None,
        filename="",
    ):
        self.message = message
        self.bot = bot
        self.command_name = command_name
        self.args = args
        self.kwargs: dict[str, Any] = dict(kwargs or {})
        self.locals: dict[str, FlowValue] = dict(locals or {})
        self.extras: dict[str, Any] = dict(extras or {})
        self.pending_view = None
        self.pending_components: list = []
        self.pending_modal = None
        self.component_handlers = None
        self.ephemeral = False
        self.deferred = False
        self.interaction = interaction
        self.filename = filename
        self.return_value = None

    def set_local(self, name: str, value) -> None:
        if isinstance(value, FlowValue):
            self.locals[name] = value
        else:
            self.locals[name] = FlowValue(value)

    def get_local(self, name: str):
        if name in self.locals:
            return self.locals[name]
        lowered = name.lower()
        for key, value in self.locals.items():
            if key.lower() == lowered:
                return value
        return None

    def child(self, **bound) -> "FlowContext":
        """Return a context for a script-function call (isolated locals)."""
        child = FlowContext(
            message=self.message,
            bot=self.bot,
            command_name=self.command_name,
            args=self.args,
            kwargs=self.kwargs,
            extras=self.extras,
            locals={},
            interaction=self.interaction,
            filename=self.filename,
        )
        child.pending_view = self.pending_view
        child.pending_components = self.pending_components
        child.pending_modal = self.pending_modal
        child.component_handlers = self.component_handlers
        child.ephemeral = self.ephemeral
        child.deferred = self.deferred
        for name, value in bound.items():
            child.set_local(name, value)
        return child

    def extra(self, name: str, default=""):
        if name in self.extras:
            return self.extras[name]
        lowered = name.lower()
        for key, value in self.extras.items():
            if key.lower() == lowered:
                return value
        return default

    # ------------------------------------------------------------------
    # Forwarded attributes (kept identical to discord.Message)
    # ------------------------------------------------------------------
    @property
    def channel(self):
        return self.message.channel

    @property
    def author(self):
        return self.message.author

    @property
    def guild(self):
        return self.message.guild

    @property
    def mentions(self):
        return self.message.mentions

    @property
    def content(self):
        return self.message.content

    @property
    def _state(self):
        return self.message._state

    def __getattr__(self, item):
        # Any other attribute delegates to the underlying message, so existing
        # script functions that touch extra fields keep working unchanged.
        return getattr(self.message, item)

    @classmethod
    def from_message(cls, message, args=""):
        """Build a :class:`FlowContext` from a raw message.

        The bot is discovered from the message's connection state when
        possible, so ``engine.run(message, code)`` keeps working.
        """
        bot = None
        try:
            bot = message._state._get_client()
        except Exception:
            bot = None
        extras = {}
        if message is not None:
            extras["message"] = message
            extras["content"] = getattr(message, "content", "") or ""
        return cls(message=message, bot=bot, args=args, extras=extras)

    @classmethod
    def for_scheduler(cls, bot, channel=None, command_name=None):
        """Build a context for scheduled tasks (no invoking message)."""
        from datetime import datetime, timezone

        channel = channel if channel is not None else getattr(bot, "scheduler_channel", None)

        class _ScheduledMessage:
            def __init__(self):
                self.channel = channel
                self.author = getattr(bot, "user", None)
                try:
                    self.guild = getattr(channel, "guild", None)
                except Exception:
                    self.guild = None
                self.mentions = []
                self.content = ""
                self.created_at = datetime.now(timezone.utc)
                self._state = _ContextState(bot)

            async def reply(self, content=None, **kwargs):
                if self.channel is not None:
                    await self.channel.send(content, **kwargs)

            async def add_reaction(self, _emoji):
                return None

            async def delete(self):
                return None

        message = _ScheduledMessage()
        # Fall back to a no-op channel when none is configured so scripts
        # using `log` (or only variables) still run.
        if message.channel is None:
            message.channel = _NullChannel()
        if message.author is None:
            message.author = _NullAuthor()
        return cls(message=message, bot=bot, command_name=command_name, args="")

    @classmethod
    def for_event(cls, bot, *, channel=None, author=None, guild=None, command_name=None, extras=None, message=None):
        """Build a context for event-triggered scripts."""
        from datetime import datetime, timezone

        extras = dict(extras or {})
        source_message = message

        class _EventMessage:
            def __init__(self):
                self.channel = channel
                self.author = author
                self.guild = guild
                self.mentions = []
                self.content = extras.get("content", getattr(source_message, "content", "") or "")
                self.created_at = getattr(source_message, "created_at", None) or datetime.now(timezone.utc)
                self.id = getattr(source_message, "id", 0)
                self._state = _ContextState(bot)

            async def reply(self, content=None, **kwargs):
                if self.channel is not None:
                    await self.channel.send(content, **kwargs)

            async def add_reaction(self, _emoji):
                return None

            async def delete(self):
                return None

        event_message = _EventMessage()
        if event_message.channel is None:
            event_message.channel = _NullChannel()
        if event_message.author is None:
            event_message.author = _NullAuthor()
        if source_message is not None:
            extras.setdefault("message", source_message)
        extras.setdefault("user", event_message.author)
        return cls(
            message=event_message,
            bot=bot,
            command_name=command_name,
            args="",
            extras=extras,
        )

    @classmethod
    def for_interaction(cls, bot, interaction, *, command_name=None, extras=None, args="", kwargs=None):
        """Build a context wrapping a Discord interaction (components / slash)."""
        extras = dict(extras or {})
        extras.setdefault("interaction", interaction)
        extras.setdefault("user", getattr(interaction, "user", None))
        extras.setdefault("value", extras.get("value", ""))
        from .slash import _InteractionMessage

        content = extras.get("content", "")
        message = _InteractionMessage(interaction, bot, content)
        return cls(
            message=message,
            bot=bot,
            command_name=command_name,
            args=args,
            kwargs=kwargs,
            extras=extras,
            interaction=interaction,
        )

    def __repr__(self):
        return (
            f"<FlowContext command_name={self.command_name!r} "
            f"author={self.author!r} channel={self.channel!r}>"
        )


class _ContextState:
    """Minimal ``_state`` shim exposing the bot as the client."""

    def __init__(self, bot):
        self._bot = bot

    def _get_client(self):
        return self._bot


class _NullChannel:
    """Fallback channel that records sends when no channel is configured."""

    def __init__(self):
        self.id = 0
        self.name = "null"
        self.mention = "#null"
        self.sent = []

    def permissions_for(self, _member):
        return None

    async def send(self, *args, **kwargs):
        self.sent.append((args, kwargs))
        return None


class _NullAuthor:
    """Fallback author used when an event provides no member."""

    def __init__(self):
        self.id = 0
        self.name = "unknown"
        self.display_name = "unknown"
        self.bot = False
        self.mention = "@unknown"
        self.roles = []
        try:
            from datetime import datetime

            self.created_at = datetime(2000, 1, 1)
            self.joined_at = None
            self.display_avatar = type("A", (), {"url": ""})()
        except Exception:
            pass

    def __str__(self):
        return self.name


# stringify is imported for callers that want a consistent conversion
__all__ = ["FlowContext", "stringify"]

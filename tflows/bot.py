"""The FlowBot Discord client.

:class:`FlowBot` extends :class:`discord.ext.commands.Bot` with a script-based
command system. Script commands are plain text programs executed by the
:class:`~tflows.engine.Engine`, while regular discord.py commands keep working
side by side.

Beyond prefix commands, :class:`FlowBot` offers first-class automation:

- ``slash=True`` / :meth:`FlowBot.slashcommand` — slash-command variants.
- ``if``/``elif``/``else``/``endif`` conditionals in scripts.
- SQLite persistent state via ``set``/``get``/``del``/``incr``.
- :meth:`FlowBot.schedule` recurring tasks (``every`` / cron).
- :meth:`FlowBot.on_event` reaction to member joins, reactions, ...
- ``cooldown`` / ``require`` guard directives in scripts.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import discord
from discord.ext import commands

from .context import FlowContext
from .engine import Engine
from .events import EVENT_MAP, EventRegistry
from .guards import CooldownManager
from .loader import load_function
from .registry import registry
from .scheduler import Scheduler
from .slash import build_slash_command, parse_slash_params
from .state import StateStore

logger = logging.getLogger("tflows.bot")


@dataclass
class ScriptCommand:
    """A script command registered on a :class:`FlowBot`.

    Attributes
    ----------
    name:
        The canonical command name.
    code:
        The script source executed when the command is invoked.
    description:
        Optional short description shown by the ``help`` command.
    aliases:
        Optional extra names that trigger the same command.
    slash:
        When ``True`` a slash-command variant is registered as well.
    slash_params:
        Normalized ``[(name, type)]`` slash parameters (empty when none).
    """

    name: str
    code: str
    description: str = ""
    aliases: tuple = field(default_factory=tuple)
    slash: bool = False
    slash_params: list = field(default_factory=list)

    @property
    def all_names(self):
        return (self.name, *self.aliases)


class FlowBot(commands.Bot):
    """A Discord bot that runs tflows scripts.

    Parameters
    ----------
    prefix:
        Command prefix used to trigger script commands.
    help_command:
        When ``True`` (default) a built-in ``help`` command lists all script
        commands. Set to ``False`` to disable it.
    log_errors:
        When ``True`` (default) errors raised inside scripts are logged.
    log_unknown_functions:
        When ``True`` (default) unknown function names are logged instead of
        silently ignored.
    case_insensitive:
        When ``True`` script command names are matched case-insensitively.
    members_intent:
        When ``True`` enables the privileged ``members`` intent, which makes
        member counts and member lists accurate.
    intents:
        Optional :class:`discord.Intents` to use instead of the defaults.
    registry:
        Optional :class:`~tflows.registry.FunctionRegistry` to use instead of
        the shared default. Useful for isolating bots from each other.
    state_path:
        Filesystem path for the SQLite state database (default
        ``"tflows.db"``). The store is created lazily on first use so bots
        that never touch state pay no cost. Pass ``None`` to disable
        persistent state (``set``/``get`` then report a useful error) or
        ``":memory:"`` for tests.
    """

    def __init__(self, prefix="!", **kwargs):
        self.help_command_enabled = kwargs.pop("help_command", True)
        self.log_errors = kwargs.pop("log_errors", True)
        self.log_unknown_functions = kwargs.pop("log_unknown_functions", True)
        case_insensitive = kwargs.pop("case_insensitive", False)
        self.members_intent = kwargs.pop("members_intent", False)
        reg = kwargs.pop("registry", None) or registry
        self._state_path = kwargs.pop("state_path", "tflows.db")
        self._state_store: StateStore | None = None

        intents = kwargs.pop("intents", None)
        if intents is None:
            intents = discord.Intents.default()
            intents.message_content = True
        if self.members_intent:
            intents.members = True

        super().__init__(
            command_prefix=prefix,
            intents=intents,
            help_command=None,
            **kwargs,
        )

        # GroupMixin resets this during super().__init__, so re-apply it.
        self.case_insensitive = case_insensitive

        self.commands_map: dict[str, str] = {}
        self.script_commands: dict[str, ScriptCommand] = {}
        self.slash_commands: dict[str, Any] = {}
        self.engine = Engine(reg)
        self.cooldowns = CooldownManager()
        self.scheduler = Scheduler(self)
        self.events = EventRegistry()

        load_function(reg)

        # Start scheduled tasks once connected; wire event dispatch.
        self.add_listener(self._tflow_on_ready, "on_ready")
        self.add_listener(self._tflow_on_member_join, "on_member_join")
        self.add_listener(self._tflow_on_member_remove, "on_member_remove")
        self.add_listener(self._tflow_on_reaction_add, "on_reaction_add")
        self.add_listener(self._tflow_on_reaction_remove, "on_reaction_remove")
        self.add_listener(self._tflow_on_typing, "on_typing")

    # ------------------------------------------------------------------
    # Persistent state (lazy so unused bots pay nothing)
    # ------------------------------------------------------------------
    @property
    def state(self) -> StateStore | None:
        """The SQLite :class:`StateStore`, created on first access.

        ``None`` when disabled via ``state_path=None``.
        """
        if self._state_path is None:
            return None
        if self._state_store is None:
            self._state_store = StateStore(self._state_path)
        return self._state_store

    async def close(self):
        try:
            await self.scheduler.stop_all()
        finally:
            if self._state_store is not None:
                self._state_store.close()
        await super().close()

    # ------------------------------------------------------------------
    # Command registration
    # ------------------------------------------------------------------
    def command(self, name, code, description="", aliases=(), slash=False, slash_params=None):
        """Register a script command.

        Parameters
        ----------
        name:
            The command name, e.g. ``"greet"``.
        code:
            The script source executed when the command runs.
        description:
            Optional short description shown by the ``help`` command and used
            as the slash-command description.
        aliases:
            Optional iterable of extra names that trigger the same command
            (prefix only).
        slash:
            When ``True`` a ``/name`` slash-command variant running the same
            script is registered alongside the prefix command.
        slash_params:
            Slash parameters: ``["name", "count: int"]``,
            ``[("count", int)]`` or ``{"count": int}``. Values map
            positionally to ``$args`` / ``$arg(n)`` and by name to
            ``$arg(name)``.

        Returns
        -------
        :class:`ScriptCommand`
            The registered command object.
        """
        aliases = tuple(aliases or ())
        params = parse_slash_params(slash_params) if slash else []
        command = ScriptCommand(
            name=name, code=code, description=description, aliases=aliases,
            slash=slash, slash_params=params,
        )
        self.script_commands[name] = command
        self.commands_map[name] = code
        for alias in aliases:
            self.commands_map[alias] = code
        if slash:
            self._register_slash(command)
        return command

    def slashcommand(self, name, code, description="", params=None, aliases=()):
        """Register a script command with a slash variant (``slash=True``)."""
        return self.command(
            name, code, description=description, aliases=aliases,
            slash=True, slash_params=params,
        )

    def _register_slash(self, command: ScriptCommand):
        try:
            app_command = build_slash_command(self, command, command.slash_params or [])
        except Exception:
            logger.exception("[tflow] Failed to build slash command %r", command.name)
            raise
        existing = self.tree.get_command(command.name)
        if existing is not None:
            self.tree.remove_command(command.name)
        self.tree.add_command(app_command)
        self.slash_commands[command.name] = app_command
        return app_command

    async def sync_commands(self, guild=None):
        """Sync slash commands with Discord. Returns the synced commands."""
        if guild is not None and not isinstance(guild, discord.Object):
            guild = discord.Object(id=int(guild))
        return await self.tree.sync(guild=guild)

    # ------------------------------------------------------------------
    # Scheduled tasks
    # ------------------------------------------------------------------
    def schedule(self, name, code, interval=None, cron=None, channel=None):
        """Register (or replace) a recurring script task.

        ``interval`` accepts seconds or duration strings (``"30s"``, ``"5m"``,
        ``"1h"``, ``"1d"``); ``cron`` accepts 5-field cron expressions. A
        leading ``every ...:`` / ``cron ...:`` header in ``code`` supplies the
        schedule when neither is passed explicitly. ``channel`` (or channel
        id) selects where ``send``/``reply`` deliver; otherwise scripts using
        only ``log``/variables still run.
        """
        if channel is not None and not hasattr(channel, "send"):
            resolved = None
            try:
                resolved = self.get_channel(int(channel))
            except Exception:
                resolved = None
            channel = resolved
        task = self.scheduler.schedule(name, code, interval=interval, cron=cron, channel=channel)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            task.start()
        return task

    def unschedule(self, name) -> bool:
        """Remove a scheduled task. Returns True when one existed."""
        return self.scheduler.unschedule(name)

    async def _tflow_on_ready(self):
        self.scheduler.start_all()

    # ------------------------------------------------------------------
    # Event triggers
    # ------------------------------------------------------------------
    def on_event(self, event, code, name=None, channel=None):
        """Run ``code`` whenever ``event`` fires (``"join"``, ``"leave"``,
        ``"react"``, ...). Returns the handler name; remove it later with
        :meth:`remove_event`. ``channel`` overrides the send destination.
        """
        handle = self.events.add(event, code, name=name, channel=channel)
        return handle

    def remove_event(self, event, name) -> bool:
        """Remove an event handler. Returns True when one existed."""
        return self.events.remove(event, name)

    async def dispatch_event(self, listener: str, *args):
        """Run all scripts registered for a discord.py listener name."""
        entries = self.events.get(listener)
        if not entries:
            return
        for entry in entries:
            handle_name, code = entry[0], entry[1]
            fixed_channel = entry[2] if len(entry) > 2 else None
            ctx = self._event_context(listener, args, fixed_channel, command_name=handle_name)
            try:
                await self.engine.run(ctx, code)
            except Exception:
                if self.log_errors:
                    logger.exception("[tflow] Error in event handler %r", handle_name)

    def _event_context(self, listener, args, fixed_channel, command_name=None) -> FlowContext:
        channel, author, guild = fixed_channel, None, None
        try:
            if listener in ("on_member_join", "on_member_remove"):
                (member,) = args
                author, guild = member, getattr(member, "guild", None)
                channel = fixed_channel or getattr(guild, "system_channel", None)
            elif listener in ("on_reaction_add", "on_reaction_remove"):
                reaction, user = args
                author = user
                message = getattr(reaction, "message", None)
                channel = fixed_channel or getattr(message, "channel", None)
                guild = getattr(message, "guild", None)
            elif listener == "on_typing":
                channel, user = args[0], args[1]
                author = user
                guild = getattr(channel, "guild", None)
                if fixed_channel is not None:
                    channel = fixed_channel
            elif listener == "on_message_event":
                (message,) = args
                author = getattr(message, "author", None)
                channel = fixed_channel or getattr(message, "channel", None)
                guild = getattr(message, "guild", None)
        except Exception:
            logger.exception("[tflow] Failed to build event context for %s", listener)
        return FlowContext.for_event(
            self, channel=channel, author=author, guild=guild, command_name=command_name
        )

    async def _tflow_on_member_join(self, member):
        await self.dispatch_event("on_member_join", member)

    async def _tflow_on_member_remove(self, member):
        await self.dispatch_event("on_member_remove", member)

    async def _tflow_on_reaction_add(self, reaction, user):
        if getattr(user, "bot", False):
            return
        await self.dispatch_event("on_reaction_add", reaction, user)

    async def _tflow_on_reaction_remove(self, reaction, user):
        if getattr(user, "bot", False):
            return
        await self.dispatch_event("on_reaction_remove", reaction, user)

    async def _tflow_on_typing(self, channel, user, when):
        if getattr(user, "bot", False):
            return
        await self.dispatch_event("on_typing", channel, user, when)

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------
    def _normalize(self, name):
        return name.lower() if self.case_insensitive else name

    def _resolve_command(self, name):
        for command in self.script_commands.values():
            if self._normalize(command.name) == name:
                return command
            for alias in command.aliases:
                if self._normalize(alias) == name:
                    return command
        return None

    def _parse_invocation(self, message):
        """Return ``(prefix, body)`` when the message uses a known prefix."""
        content = message.content
        prefix = self.command_prefix

        if callable(prefix):
            return None

        prefixes = prefix if isinstance(prefix, (list, tuple)) else [prefix]
        for candidate in prefixes:
            if content.startswith(candidate):
                return candidate, content[len(candidate) :].strip()
        return None

    async def on_message(self, message):
        if message.author.bot:
            return

        parsed = self._parse_invocation(message)
        if parsed is None:
            await self.dispatch_event("on_message_event", message)
            if self.is_ready():
                await self.process_commands(message)
            return

        prefix, body = parsed
        if not body:
            return

        parts = body.split(None, 1)
        raw_name = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        name = self._normalize(raw_name)

        # Built-in help command (only when the user has not defined their own).
        if self.help_command_enabled and name == "help" and self._resolve_command(name) is None:
            await self.send_help(message, query=args.strip() or None)
            return

        command = self._resolve_command(name)
        if command is not None:
            ctx = FlowContext(message=message, bot=self, command_name=command.name, args=args)
            try:
                await self.engine.run(ctx, command.code)
            except Exception:
                if self.log_errors:
                    logger.exception("[tflow] Error running command %r", command.name)
            return

        await self.dispatch_event("on_message_event", message)
        # Not a script command; fall through to discord.py commands. Only
        # after the bot is connected (so the event loop is available).
        if self.is_ready():
            await self.process_commands(message)

    # ------------------------------------------------------------------
    # Built-in help command
    # ------------------------------------------------------------------
    async def send_help(self, message, query=None):
        """Send the built-in help message listing registered script commands."""
        prefix = self.command_prefix
        prefix = prefix[0] if isinstance(prefix, (list, tuple)) else prefix

        if query:
            command = self._resolve_command(self._normalize(query))
            if command is None:
                await message.channel.send(f"No command named `{query}` was found.")
                return
            embed = discord.Embed(
                title=f"Command: {prefix}{command.name}", color=discord.Color.blurple()
            )
            if command.description:
                embed.add_field(name="Description", value=command.description, inline=False)
            embed.add_field(name="Usage", value=f"{prefix}{command.name} <arguments>", inline=False)
            if command.aliases:
                embed.add_field(
                    name="Aliases", value=", ".join(f"`{a}`" for a in command.aliases), inline=False
                )
            if command.slash:
                params = ", ".join(n for n, _ in command.slash_params) or "none"
                embed.add_field(name="Slash", value=f"/{command.name} (params: {params})", inline=False)
            embed.add_field(name="Script", value=f"```\n{command.code.strip()}\n```", inline=False)
            await message.channel.send(embed=embed)
            return

        if not self.script_commands:
            await message.channel.send("No script commands registered yet.")
            return

        embed = discord.Embed(
            title="Script Commands",
            description=f"Use `{prefix}help <command>` for details.",
            color=discord.Color.blurple(),
        )
        for command in sorted(self.script_commands.values(), key=lambda c: c.name):
            aliases = f" *(aliases: {', '.join(command.aliases)})*" if command.aliases else ""
            slash = " *(slash)*" if command.slash else ""
            embed.add_field(
                name=f"{prefix}{command.name}",
                value=(command.description or "No description provided.") + aliases + slash,
                inline=False,
            )
        await message.channel.send(embed=embed)


# Re-export the friendly event names so users can discover them.
EVENT_NAMES = sorted(set(EVENT_MAP))

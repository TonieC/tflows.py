"""The FlowBot Discord client.

:class:`FlowBot` extends :class:`discord.ext.commands.Bot` with a script-based
command system. Script commands are plain text programs executed by the
:class:`~tflows.engine.Engine`, while regular discord.py commands keep working
side by side.
"""

import logging
from dataclasses import dataclass, field

import discord
from discord.ext import commands

from .context import FlowContext
from .engine import Engine
from .loader import load_function
from .registry import registry

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
    """

    name: str
    code: str
    description: str = ""
    aliases: tuple = field(default_factory=tuple)

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
    """

    def __init__(self, prefix="!", **kwargs):
        self.help_command_enabled = kwargs.pop("help_command", True)
        self.log_errors = kwargs.pop("log_errors", True)
        self.log_unknown_functions = kwargs.pop("log_unknown_functions", True)
        case_insensitive = kwargs.pop("case_insensitive", False)
        self.members_intent = kwargs.pop("members_intent", False)
        reg = kwargs.pop("registry", None) or registry

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

        self.commands_map = {}
        self.script_commands = {}
        self.engine = Engine(reg)

        load_function(reg)

    # ------------------------------------------------------------------
    # Command registration
    # ------------------------------------------------------------------
    def command(self, name, code, description="", aliases=()):
        """Register a script command.

        Parameters
        ----------
        name:
            The command name, e.g. ``"greet"``.
        code:
            The script source executed when the command runs.
        description:
            Optional short description shown by the ``help`` command.
        aliases:
            Optional iterable of extra names that trigger the same command.

        Returns
        -------
        :class:`ScriptCommand`
            The registered command object.
        """
        aliases = tuple(aliases or ())
        command = ScriptCommand(name=name, code=code, description=description, aliases=aliases)
        self.script_commands[name] = command
        self.commands_map[name] = code
        for alias in aliases:
            self.commands_map[alias] = code
        return command

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

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------
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
            embed.add_field(
                name=f"{prefix}{command.name}",
                value=(command.description or "No description provided.") + aliases,
                inline=False,
            )
        await message.channel.send(embed=embed)

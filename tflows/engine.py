"""The tflows script interpreter.

The :class:`Engine` executes text scripts line by line. Each line is either a
call to a registered function (``send hello world``), a ``$variable`` template
that gets resolved inline, an ``embed``/``endembed`` block, a conditional
(``if``/``elif``/``else``/``endif``), or a declarative guard
(``cooldown``/``require``).
"""

import asyncio
import logging
import re

import discord

from .conditionals import evaluate_condition, is_else, is_endif, parse_if_header
from .context import FlowContext
from .events import parse_on_header
from .guards import check_permission, parse_cooldown, parse_require
from .scheduler import parse_cron_header, parse_every_header
from .utils import parse_color

logger = logging.getLogger("tflows.engine")

# Matches $variable and $variable(arg, ...). Parenthesized arguments are
# intentionally kept flat (no nesting) so replacement stays predictable.
_VAR_PATTERN = re.compile(r"\$(\w+)(?:\(([^()]*)\))?")

_EMBED_KEYS = ("title", "desc", "footer", "color", "thumbnail", "image", "timestamp", "author")

_COMMENT_PREFIXES = ("//", "#", "--")


class Engine:
    """Executes tflows scripts against a registry of functions and variables.

    Parameters
    ----------
    registry:
        The :class:`~tflows.registry.FunctionRegistry` to resolve against.
    """

    def __init__(self, registry):
        self.registry = registry

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_comment(line):
        return line.startswith(_COMMENT_PREFIXES)

    @staticmethod
    def _indent(raw_line):
        return len(raw_line.expandtabs(4)) - len(raw_line.expandtabs(4).lstrip())

    def _log_errors(self, ctx):
        bot = getattr(ctx, "bot", None)
        return getattr(bot, "log_errors", True) if bot is not None else True

    @staticmethod
    def _is_schedule_header(stripped):
        # Tolerated so scheduled scripts run verbatim when executed manually.
        return parse_every_header(stripped) is not None or parse_cron_header(stripped) is not None

    @staticmethod
    def _is_event_header(stripped):
        # Tolerated so event scripts run verbatim when executed manually.
        return parse_on_header(stripped) is not None

    # ------------------------------------------------------------------
    # Variable resolution
    # ------------------------------------------------------------------
    async def resolve_var(self, ctx, name, args=""):
        """Resolve a single ``$name(args)`` variable to a string.

        Returns ``None`` when the variable is not registered, so callers can
        leave the original text untouched.
        """
        handler = self.registry.get_var(name)
        if handler is None:
            return None

        result = handler(ctx, args)
        if asyncio.iscoroutine(result):
            result = await result
        if result is None:
            return ""
        return str(result)

    async def replace_vars(self, ctx, text):
        """Replace every ``$variable`` / ``$variable(args)`` occurrence in text.

        Unknown variables are left as-is so typos do not silently corrupt
        output. Replacement happens from the last match to the first so that a
        resolved value is never re-scanned for new variables.
        """
        if text is None:
            return ""

        matches = list(_VAR_PATTERN.finditer(text))
        for match in reversed(matches):
            name = match.group(1)
            args = match.group(2) or ""
            replacement = await self.resolve_var(ctx, name, args)
            if replacement is None:
                continue
            start, end = match.span()
            text = text[:start] + replacement + text[end:]

        return text

    # ------------------------------------------------------------------
    # Embed blocks
    # ------------------------------------------------------------------
    def _grab(self, block, key):
        match = re.search(rf"\${key}\[(.*?)\]", block, re.DOTALL)
        return match.group(1).strip() if match else None

    def _apply_embed(self, embed, key, value):
        """Apply a resolved embed directive to a discord.Embed instance."""
        key = key.lower()

        if key in ("title", "author"):
            if value:
                if key == "title":
                    embed.title = value
                else:
                    embed.set_author(name=value)
            return

        if key == "desc":
            embed.description = value or embed.description
            return

        if key == "footer":
            if value:
                embed.set_footer(text=value)
            return

        if key == "color":
            color = parse_color(value)
            if color is not None:
                embed.color = discord.Color(color)
            return

        if key == "thumbnail":
            if value:
                embed.set_thumbnail(url=value)
            return

        if key == "image":
            if value:
                embed.set_image(url=value)
            return

    async def parse_embed(self, ctx, block):
        """Parse and send an ``embed``/``endembed`` block."""
        block = block.replace("\r\n", "\n").strip()
        embed = discord.Embed()

        values = {}
        for key in _EMBED_KEYS:
            values[key] = self._grab(block, key)

        clean = re.sub(
            r"\$(title|desc|footer|color|thumbnail|image|timestamp|author)\[.*?\]",
            "",
            block,
            flags=re.DOTALL,
        ).strip()

        for key, raw in values.items():
            if not raw:
                continue
            resolved = await self.replace_vars(ctx, raw)
            if key == "timestamp":
                embed.timestamp = ctx.message.created_at
            else:
                self._apply_embed(embed, key, resolved)

        # Fall back to whatever text is left when no explicit $desc[...] given.
        if not values.get("desc") and clean:
            embed.description = await self.replace_vars(ctx, clean)

        await ctx.channel.send(embed=embed)

    # ------------------------------------------------------------------
    # Guards (cooldown / require directives)
    # ------------------------------------------------------------------
    async def _handle_cooldown(self, ctx, stripped, state) -> bool | None:
        """Enforce a ``cooldown`` line. Returns False to abort, True to continue,
        None when the line is not a cooldown directive."""
        low = stripped.lower()
        if low != "cooldown" and not low.startswith("cooldown "):
            return None
        parsed = parse_cooldown(stripped)
        if parsed is None:
            logger.warning("[tflow] Invalid cooldown syntax: %s", stripped)
            await self._notify(ctx, f"Invalid cooldown syntax: `{stripped}` (expected e.g. `cooldown 5s per user`)")
            return True
        if state["cooldown_seen"]:
            return True  # first cooldown line wins
        state["cooldown_seen"] = True
        seconds, scope = parsed
        manager = self._cooldown_manager(ctx)
        if manager is None:
            return True
        from .guards import _scope_key

        command = getattr(ctx, "command_name", None) or "global"
        remaining = manager.check(command, scope, _scope_key(ctx, scope), seconds)
        if remaining > 0:
            await self._notify(
                ctx, f"Please wait {remaining:.0f}s before using `{command}` again."
            )
            return False
        return True

    async def _handle_require(self, ctx, stripped) -> bool | None:
        """Enforce a ``require`` line. Returns False to abort, True to continue,
        None when the line is not a require directive."""
        low = stripped.lower()
        if low != "require" and not low.startswith("require "):
            return None
        parsed = parse_require(stripped)
        if parsed is None:
            logger.warning("[tflow] Invalid require syntax: %s", stripped)
            await self._notify(
                ctx,
                f"Invalid require syntax: `{stripped}` "
                "(expected e.g. `require manage_messages`, `require role Mod`, `require owner`)",
            )
            return False  # fail closed on unparseable requirements
        kind, value = parsed
        if not check_permission(ctx, kind, value):
            await self._notify(ctx, "You do not have permission to use this command.")
            return False
        return True

    @staticmethod
    def _cooldown_manager(ctx):
        bot = getattr(ctx, "bot", None)
        manager = getattr(bot, "cooldowns", None) if bot is not None else None
        if manager is not None:
            return manager
        # Standalone engine use: keep an ephemeral manager on the context.
        if bot is None:
            return None
        from .guards import CooldownManager

        bot.cooldowns = CooldownManager()
        return bot.cooldowns

    async def _notify(self, ctx, text: str) -> None:
        try:
            await ctx.channel.send(text)
        except Exception:
            logger.exception("[tflow] Failed to send notice")

    # ------------------------------------------------------------------
    # Main interpreter loop
    # ------------------------------------------------------------------
    async def run(self, ctx, code):
        """Execute a script.

        ``ctx`` may be a raw :class:`discord.Message`, in which case it is
        wrapped in a :class:`FlowContext`, or a :class:`FlowContext` directly.

        Supports ``if``/``elif``/``else``/``endif`` conditionals (nestable),
        ``cooldown``/``require`` guard directives, and tolerates leading
        ``every``/``cron``/``on`` headers from scheduled/event scripts.
        """
        if not isinstance(ctx, FlowContext):
            ctx = FlowContext.from_message(ctx)

        log_errors = self._log_errors(ctx)
        lines = (code or "").split("\n")
        stack: list[dict] = []  # if-frames
        guard_state = {"cooldown_seen": False}
        i = 0

        def active() -> bool:
            return all(frame["branch_active"] for frame in stack)

        def close_dedented(indent: int, stripped: str) -> None:
            # `else`/`elif`/`endif` at any indent belong to their block.
            header = parse_if_header(stripped)
            if is_else(stripped) or is_endif(stripped) or (header is not None and header[0] == "elif"):
                return
            while stack and indent <= stack[-1]["if_indent"] and stack[-1]["saw_body"]:
                stack.pop()

        while i < len(lines):
            raw = lines[i]
            stripped = raw.strip()
            indent = self._indent(raw)

            if not stripped or self._is_comment(stripped):
                i += 1
                continue

            # ----- conditional headers -----
            if_header = parse_if_header(stripped)
            if if_header is not None and if_header[0] == "if":
                close_dedented(indent, stripped)
                # A nested `if` is itself an indented body line for outer frames.
                for frame in stack:
                    if indent > frame["if_indent"]:
                        frame["saw_body"] = True
                parent_active = active()
                _keyword, expr = if_header
                if not expr:
                    logger.warning("[tflow] Empty condition in line: %s", stripped)
                    result = False
                elif parent_active:
                    try:
                        result = await evaluate_condition(ctx, self, expr)
                    except Exception:
                        if log_errors:
                            logger.exception("[tflow] Failed to evaluate condition: %s", expr)
                        result = False
                else:
                    result = False
                stack.append(
                    {
                        "if_indent": indent,
                        "parent_active": parent_active,
                        "matched": bool(result) and parent_active,
                        "branch_active": bool(result) and parent_active,
                        "else_seen": False,
                        "saw_body": False,
                    }
                )
                i += 1
                continue

            if is_endif(stripped):
                if stack:
                    # Only treat as a terminator when it closes a block at a
                    # compatible indent; otherwise fall through to dispatch.
                    if indent <= stack[-1]["if_indent"] or not stack[-1]["saw_body"]:
                        stack.pop()
                        i += 1
                        continue
                # Outside any if-block (or incompatible): unknown function path.
                if not stack and active():
                    try:
                        await self.execute_line(ctx, stripped)
                    except Exception:
                        if log_errors:
                            logger.exception("[tflow] Error in line: %s", stripped)
                i += 1
                continue

            if is_else(stripped) or (if_header is not None and if_header[0] == "elif"):
                if not stack:
                    logger.warning("[tflow] '%s' without matching 'if'", stripped)
                    i += 1
                    continue
                frame = stack[-1]
                if frame["else_seen"]:
                    logger.warning("[tflow] Multiple 'else' branches for one 'if'")
                    frame["branch_active"] = False
                    i += 1
                    continue
                if is_else(stripped):
                    frame["else_seen"] = True
                    frame["branch_active"] = frame["parent_active"] and not frame["matched"]
                    if frame["branch_active"]:
                        frame["matched"] = True
                else:
                    _kw, expr = parse_if_header(stripped)
                    if frame["parent_active"] and not frame["matched"]:
                        try:
                            result = await evaluate_condition(ctx, self, expr)
                        except Exception:
                            if log_errors:
                                logger.exception("[tflow] Failed to evaluate condition: %s", expr)
                            result = False
                        frame["branch_active"] = bool(result)
                        if result:
                            frame["matched"] = True
                    else:
                        frame["branch_active"] = False
                i += 1
                continue

            # Dedent closes blocks whose body was indented.
            close_dedented(indent, stripped)
            is_active = active()
            if stack and indent > stack[-1]["if_indent"] and stripped:
                stack[-1]["saw_body"] = True

            # ----- embed block -----
            if stripped == "embed":
                i += 1
                block = []
                while i < len(lines):
                    if lines[i].strip() == "endembed":
                        break
                    block.append(lines[i])
                    i += 1
                if is_active:
                    try:
                        await self.parse_embed(ctx, "\n".join(block))
                    except Exception:
                        if log_errors:
                            logger.exception("[tflow] Failed to render embed block")
                i += 1
                continue

            # ----- schedule / event headers tolerated as no-ops -----
            if self._is_schedule_header(stripped) or self._is_event_header(stripped):
                i += 1
                continue

            # ----- guard directives -----
            if is_active:
                cooldown = await self._handle_cooldown(ctx, stripped, guard_state)
                if cooldown is False:
                    return
                if cooldown is True:
                    i += 1
                    continue
                required = await self._handle_require(ctx, stripped)
                if required is False:
                    return
                if required is True:
                    i += 1
                    continue

            # ----- normal instruction -----
            if is_active:
                try:
                    await self.execute_line(ctx, stripped)
                except Exception:
                    if log_errors:
                        logger.exception("[tflow] Error in line: %s", stripped)

            i += 1

    async def execute_line(self, ctx, line):
        """Resolve variables in ``line`` and dispatch it as a function call."""
        line = await self.replace_vars(ctx, line)

        parts = line.split(" ", 1)
        name = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        func = self.registry.get(name)
        if func is None:
            logger.info("[tflow] Unknown function: %s", name)
            return

        result = func(ctx, args)
        if asyncio.iscoroutine(result):
            await result

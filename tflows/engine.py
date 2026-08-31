"""The tflows script interpreter.

The :class:`Engine` executes text scripts line by line. Each line is either a
call to a registered function (``send hello world``), a ``$variable`` template
that gets resolved inline, or an ``embed``/``endembed`` block.
"""

import asyncio
import logging
import re

import discord

from .context import FlowContext
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

    def _log_errors(self, ctx):
        bot = getattr(ctx, "bot", None)
        return getattr(bot, "log_errors", True) if bot is not None else True

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
    # Main interpreter loop
    # ------------------------------------------------------------------
    async def run(self, ctx, code):
        """Execute a script.

        ``ctx`` may be a raw :class:`discord.Message`, in which case it is
        wrapped in a :class:`FlowContext`, or a :class:`FlowContext` directly.
        """
        if not isinstance(ctx, FlowContext):
            ctx = FlowContext.from_message(ctx)

        log_errors = self._log_errors(ctx)
        lines = (code or "").split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if not line or self._is_comment(line):
                i += 1
                continue

            # ----- embed block -----
            if line == "embed":
                i += 1
                block = []
                while i < len(lines):
                    if lines[i].strip() == "endembed":
                        break
                    block.append(lines[i])
                    i += 1

                try:
                    await self.parse_embed(ctx, "\n".join(block))
                except Exception:
                    if log_errors:
                        logger.exception("[tflow] Failed to render embed block")
                i += 1
                continue

            # ----- normal instruction -----
            try:
                await self.execute_line(ctx, line)
            except Exception:
                if log_errors:
                    logger.exception("[tflow] Error in line: %s", line)

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

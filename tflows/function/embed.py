import re

import discord

from ..engine import Engine
from ..utils import parse_color

_EMBED_KEYS = ("title", "desc", "footer", "color", "thumbnail", "image", "author", "timestamp")


def _parse_entries(block):
    """Split an embed block into ``(key, value)`` entries.

    Entries can be separated by newlines or by ``|`` so the single-line
    ``$embed<...>`` form stays convenient.
    """
    entries = []
    for part in re.split(r"\n|\|", block):
        part = part.strip()
        if not part or ":" not in part:
            continue
        key, value = part.split(":", 1)
        entries.append((key.strip().lower(), value.strip()))
    return entries


def setup(registry):

    @registry.register("embed")
    async def embed(ctx, args):
        raw = args.strip()
        match = re.search(r"\$embed<([\s\S]*?)>", raw)
        if not match:
            await ctx.channel.send("Invalid embed format")
            return

        block = match.group(1)
        e = discord.Embed()

        engine = getattr(getattr(ctx, "bot", None), "engine", None)
        if engine is None:
            engine = Engine(registry)

        fields = []

        for key, value in _parse_entries(block):
            if key == "field":
                parts = [p.strip() for p in value.split(";")]
                name = parts[0] if len(parts) > 0 else ""
                field_value = parts[1] if len(parts) > 1 else ""
                inline = len(parts) > 2 and parts[2].lower() in ("true", "1", "yes", "y")
                fields.append((name, field_value, inline))
                continue

            resolved = await engine.replace_vars(ctx, value)

            if key == "title":
                e.title = resolved
            elif key in ("desc", "description"):
                e.description = resolved
            elif key == "footer":
                e.set_footer(text=resolved)
            elif key == "color":
                color = parse_color(resolved)
                if color is not None:
                    e.color = discord.Color(color)
            elif key == "thumbnail":
                e.set_thumbnail(url=resolved)
            elif key == "image":
                e.set_image(url=resolved)
            elif key == "author":
                e.set_author(name=resolved)
            elif key == "timestamp":
                e.timestamp = ctx.message.created_at

        for name, field_value, inline in fields:
            e.add_field(name=name, value=field_value, inline=inline)

        await ctx.channel.send(embed=e)

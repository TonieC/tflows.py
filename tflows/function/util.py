"""General-purpose script helpers: choose, config, delay."""

import random

from ..runtime import stringify
from ..utils import format_duration, parse_duration


def _split_choices(args: str) -> list[str]:
    text = (args or "").strip()
    if not text:
        return []
    if "|" in text:
        parts = [p.strip() for p in text.split("|")]
    elif "," in text:
        parts = [p.strip() for p in text.split(",")]
    else:
        parts = [p.strip() for p in text.split()]
    return [p.strip("'\"") for p in parts if p]


def setup(registry):
    @registry.register("choose")
    async def choose_cmd(ctx, args):
        choices = _split_choices(args)
        if not choices:
            return ""
        picked = random.choice(choices)
        await ctx.channel.send(picked)
        return picked

    @registry.register_var("choose")
    def choose_var(ctx, args):
        choices = _split_choices(args)
        if not choices:
            return ""
        return random.choice(choices)

    @registry.register("config")
    async def config_cmd(ctx, args):
        bot = getattr(ctx, "bot", None)
        if bot is None:
            return ""
        cfg = getattr(bot, "config", None)
        if cfg is None:
            bot.config = {}
            cfg = bot.config
        parts = (args or "").split(None, 1)
        if not parts:
            if not cfg:
                return ""
            await ctx.channel.send(", ".join(f"{k}={v}" for k, v in cfg.items()))
            return dict(cfg)
        key = parts[0]
        if len(parts) == 1:
            value = cfg.get(key, "")
            if value != "" and value is not None:
                await ctx.channel.send(stringify(value))
            return value
        cfg[key] = parts[1]
        return parts[1]

    @registry.register_var("config")
    def config_var(ctx, args):
        bot = getattr(ctx, "bot", None)
        cfg = getattr(bot, "config", None) if bot is not None else None
        if not cfg:
            return ""
        key = (args or "").strip().strip("'\"")
        if not key:
            return ", ".join(str(k) for k in cfg)
        if key in cfg:
            return stringify(cfg[key])
        lowered = key.lower()
        for candidate, item in cfg.items():
            if str(candidate).lower() == lowered:
                return stringify(item)
        return ""

    @registry.register_var("duration")
    def duration_var(ctx, args):
        seconds = parse_duration(args)
        if seconds is None:
            return ""
        return format_duration(seconds)

import asyncio

from ..utils import parse_duration

_DEFAULT_MAX_WAIT = 300


def _max_wait(ctx) -> float:
    bot = getattr(ctx, "bot", None)
    value = getattr(bot, "max_wait", None) if bot is not None else None
    try:
        return float(value) if value is not None else _DEFAULT_MAX_WAIT
    except (TypeError, ValueError):
        return _DEFAULT_MAX_WAIT


def setup(registry):

    @registry.register("wait")
    async def wait(ctx, args):
        seconds = parse_duration(args)
        if seconds is None:
            return
        cap = _max_wait(ctx)
        if cap >= 0:
            seconds = min(seconds, cap)
        await asyncio.sleep(max(0.0, seconds))

    registry.register_alias("delay", "wait")

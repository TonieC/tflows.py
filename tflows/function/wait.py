import asyncio

from ..utils import parse_duration

_MAX_WAIT = 300


def setup(registry):

    @registry.register("wait")
    async def wait(ctx, args):
        seconds = parse_duration(args)
        if seconds is None:
            return
        await asyncio.sleep(min(seconds, _MAX_WAIT))

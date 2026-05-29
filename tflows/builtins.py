from .registry import registry

import tflows.function.time  

@registry.register("send")
async def send(ctx, args):
    await ctx.channel.send(args)


@registry.register("log")
async def log(ctx, args):
    print(f"[tflow log] {args}")
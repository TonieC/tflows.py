def setup(registry):

    @registry.register("ping")
    async def ping(ctx, args):
        latency = ctx._state._get_client().latency * 1000
        await ctx.channel.send(f"Pong! {latency:.2f}ms")
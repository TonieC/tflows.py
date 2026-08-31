def setup(registry):

    @registry.register("ping")
    async def ping(ctx, args):
        latency = ctx._state._get_client().latency * 1000
        await ctx.channel.send(f"Pong! {latency:.2f}ms")

    def ping_var(ctx, args):
        latency = ctx._state._get_client().latency * 1000
        return f"{latency:.2f}ms"

    registry.register_var("ping", ping_var)

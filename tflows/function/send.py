def setup(registry):

    @registry.register("send")
    async def send(ctx, args):
        await ctx.channel.send(args)
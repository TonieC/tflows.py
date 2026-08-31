def setup(registry):

    @registry.register("reply")
    async def reply(ctx, args):
        if args:
            await ctx.message.reply(args)

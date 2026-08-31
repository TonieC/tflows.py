def setup(registry):

    @registry.register("react")
    async def react(ctx, args):
        for emoji in (args or "").split():
            await ctx.message.add_reaction(emoji)

def setup(registry):

    @registry.register("delete")
    async def delete(ctx, args):
        try:
            await ctx.message.delete()
        except Exception:
            pass

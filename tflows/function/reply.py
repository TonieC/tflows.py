def setup(registry):

    @registry.register("reply")
    async def reply(ctx, args):
        kwargs = {}
        try:
            from ..components import build_view

            view = build_view(ctx)
        except Exception:
            view = getattr(ctx, "pending_view", None)
        if view is not None:
            kwargs["view"] = view
        if getattr(ctx, "ephemeral", False):
            kwargs["ephemeral"] = True
        if args or kwargs:
            await ctx.message.reply(args if args else None, **kwargs)

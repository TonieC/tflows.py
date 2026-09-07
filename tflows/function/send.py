def setup(registry):

    @registry.register("send")
    async def send(ctx, args):
        kwargs = {}
        view = None
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
            await ctx.channel.send(args if args else None, **kwargs)

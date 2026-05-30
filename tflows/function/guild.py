def setup(registry):

    @registry.register("server")
    async def server(ctx, args):

        g = ctx.guild

        # no args
        if not args:
            return g.name

        arg = args.strip().lower()

        if arg == "name":
            return g.name

        if arg == "boost":
            return str(g.premium_subscription_count or 0)

        if arg == "boostlvl":
            return str(g.premium_tier)

        return ""
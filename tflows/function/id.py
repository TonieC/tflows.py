def setup(registry):

    def id_var(ctx, arg):

        if arg in (None, "", "user"):
            return str(ctx.author.id)

        if arg == "mention":
            if ctx.mentions:
                return str(ctx.mentions[0].id)
            return str(ctx.author.id)

        if arg == "act":
            if ctx.mentions:
                return str(ctx.mentions[0].id)
            return str(ctx.author.id)

        return str(ctx.author.id)

    registry.register_var("id", id_var)
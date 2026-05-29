def setup(registry):

    def image_var(ctx, arg):

        # -----------------------
        # AUTHOR IMAGE
        # -----------------------
        if arg in (None, "", "user"):
            return str(ctx.author.display_avatar.url)

        # -----------------------
        # MENTION IMAGE
        # -----------------------
        if arg == "mention":
            if ctx.mentions:
                return str(ctx.mentions[0].display_avatar.url)
            return str(ctx.author.display_avatar.url)

        # -----------------------
        # ACT MODE
        # -----------------------
        if arg == "act":
            if ctx.mentions:
                return str(ctx.mentions[0].display_avatar.url)
            return str(ctx.author.display_avatar.url)

        # -----------------------
        # FALLBACK
        # -----------------------
        return str(ctx.author.display_avatar.url)

    registry.register_var("image", image_var)
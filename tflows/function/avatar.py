# tflows/function/avatar.py

def setup(registry):

    def avatar_var(ctx, arg):

        # -----------------------
        # AUTHOR AVATAR
        # -----------------------
        if arg in (None, "", "user"):
            return str(ctx.author.display_avatar.url)

        # -----------------------
        # MENTION AVATAR
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
        # DEFAULT
        # -----------------------
        return str(ctx.author.display_avatar.url)

    registry.register_var("avatar", avatar_var)
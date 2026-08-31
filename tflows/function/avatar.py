# tflows/function/avatar.py


def avatar_var(ctx, args):
    arg = (args or "").strip().lower()

    if arg in ("mention", "act") and ctx.mentions:
        return str(ctx.mentions[0].display_avatar.url)

    return str(ctx.author.display_avatar.url)


def setup(registry):
    registry.register_var("avatar", avatar_var)

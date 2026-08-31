# tflows/function/id.py


def id_var(ctx, args):
    arg = (args or "").strip().lower()

    if arg in ("mention", "act") and ctx.mentions:
        return str(ctx.mentions[0].id)

    return str(ctx.author.id)


def setup(registry):
    registry.register_var("id", id_var)

def _guild_info(ctx, args):
    g = ctx.guild
    if g is None:
        return ""

    arg = (args or "").strip().lower()

    if arg in ("", "name"):
        return str(g.name)

    if arg == "id":
        return str(g.id)

    if arg in ("boost", "boosts"):
        return str(g.premium_subscription_count or 0)

    if arg in ("boostlvl", "boostlevel"):
        return str(g.premium_tier)

    if arg in ("members", "membercount"):
        return str(g.member_count)

    if arg == "icon":
        return str(g.icon.url) if g.icon else ""

    if arg == "owner":
        return g.owner.mention if g.owner else ""

    if arg in ("created", "createdat"):
        return str(g.created_at.date())

    if arg in ("desc", "description"):
        return g.description or ""

    return str(g.name)


def setup(registry):

    @registry.register("server")
    async def server(ctx, args):
        return _guild_info(ctx, args)

    registry.register_var("server", _guild_info)
    registry.register_var("guild", _guild_info)

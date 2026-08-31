def _membercount_info(ctx, args):
    g = ctx.guild
    if g is None:
        return ""

    arg = (args or "").strip().lower()

    if arg in ("", "all"):
        return str(g.member_count)

    members = list(g.members)

    if arg == "bots":
        return str(sum(1 for m in members if m.bot))

    if arg == "user":
        return str(sum(1 for m in members if not m.bot))

    return str(g.member_count)


def setup(registry):

    @registry.register("membercount")
    async def membercount(ctx, args):
        return _membercount_info(ctx, args)

    registry.register_var("membercount", _membercount_info)

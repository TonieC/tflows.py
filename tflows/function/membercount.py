def setup(registry):

    @registry.register("membercount")
    async def membercount(ctx, args):

        guild = ctx.guild
        members = guild.members

        # no args = all
        if not args:
            return str(guild.member_count)

        arg = args.strip().lower()

        if arg == "all":
            return str(guild.member_count)

        if arg == "bots":
            count = sum(1 for m in members if m.bot)
            return str(count)

        if arg == "user":
            count = sum(1 for m in members if not m.bot)
            return str(count)

        return ""
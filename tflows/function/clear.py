from ..guards import check_permission


def setup(registry):

    @registry.register("clear")
    async def clear(ctx, args):
        message = ctx.message
        channel = ctx.channel

        try:
            count = int((args or "5").strip().split()[0])
        except (ValueError, IndexError):
            count = 5
        count = max(1, min(count, 100))

        if not check_permission(ctx, "perm", "manage_messages"):
            await channel.send("You do not have permission to clear messages.")
            return

        if ctx.guild is not None:
            me = getattr(ctx.guild, "me", None)
            permissions = channel.permissions_for(me) if me is not None else None
            if permissions is not None and not getattr(permissions, "manage_messages", False):
                await channel.send("I need the **Manage Messages** permission to clear messages.")
                return

        try:
            await message.delete()
        except Exception:
            pass

        purge = getattr(channel, "purge", None)
        if callable(purge):
            try:
                await purge(limit=count, check=lambda m: m.id != message.id)
            except Exception:
                pass

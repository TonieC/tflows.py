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

        if ctx.guild is not None:
            permissions = channel.permissions_for(ctx.guild.me)
            if not permissions.manage_messages:
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

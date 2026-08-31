def _channel_info(ctx, args):
    channel = ctx.channel
    if channel is None:
        return ""

    arg = (args or "").strip().lower()

    if arg in ("", "name"):
        return str(getattr(channel, "name", ""))

    if arg == "id":
        return str(channel.id)

    if arg == "mention":
        return str(getattr(channel, "mention", ""))

    if arg in ("topic", "description"):
        return str(getattr(channel, "topic", "") or "")

    if arg == "nsfw":
        return "true" if getattr(channel, "nsfw", False) else "false"

    if arg in ("type", "kind"):
        return str(getattr(channel, "type", ""))

    if arg == "position":
        return str(getattr(channel, "position", ""))

    if arg in ("created", "createdat"):
        created = getattr(channel, "created_at", None)
        return str(created.date()) if created else ""

    if arg == "category":
        category = getattr(channel, "category", None)
        return str(category.name) if category else ""

    return str(getattr(channel, "name", ""))


def setup(registry):
    registry.register_var("channel", _channel_info)

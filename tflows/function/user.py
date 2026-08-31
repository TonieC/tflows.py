def _user_info(ctx, args):
    author = ctx.author
    arg = (args or "").strip().lower()

    if arg in ("", "name", "username"):
        return str(author.name)

    if arg in ("display", "displayname", "nick"):
        return str(getattr(author, "display_name", author.name))

    if arg in ("id", "userid"):
        return str(author.id)

    if arg == "mention":
        return str(author.mention)

    if arg in ("avatar", "image", "pfp"):
        return str(author.display_avatar.url)

    if arg in ("created", "createdat"):
        return str(author.created_at.date())

    if arg in ("joined", "joinedat"):
        joined = getattr(author, "joined_at", None)
        return str(joined.date()) if joined else ""

    if arg == "bot":
        return "true" if author.bot else "false"

    if arg in ("tag", "full"):
        return str(author)

    return str(author.name)


def setup(registry):
    registry.register_var("user", _user_info)
    registry.register_var("author", _user_info)

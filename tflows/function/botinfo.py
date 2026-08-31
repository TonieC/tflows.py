import time

START_TIME = time.time()


def _bot_info(ctx, args):
    bot = getattr(ctx, "bot", None)
    if bot is None:
        try:
            bot = ctx._state._get_client()
        except Exception:
            bot = None

    arg = (args or "").strip().lower()

    if bot is None or getattr(bot, "user", None) is None:
        return ""

    user = bot.user

    if arg in ("", "name", "username"):
        return str(user.name)

    if arg == "id":
        return str(user.id)

    if arg == "mention":
        return str(user.mention)

    if arg == "avatar":
        return str(user.display_avatar.url)

    if arg in ("status", "presence"):
        return str(getattr(bot, "status", ""))

    if arg == "ping":
        latency = getattr(bot, "latency", 0) * 1000
        return f"{latency:.2f}ms"

    if arg == "uptime":
        total = int(time.time() - START_TIME)
        return f"{total}s"

    return str(user.name)


def setup(registry):
    registry.register_var("bot", _bot_info)

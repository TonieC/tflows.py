class FunctionRegistry:
    def __init__(self):
        self.functions = {}
        self.vars = {}

    # -----------------------
    # FUNCTIONS
    # -----------------------
    def register(self, name, func=None):
        if func is None:
            def wrapper(f):
                self.functions[name] = f
                return f
            return wrapper

        self.functions[name] = func
        return func

    def get(self, name):
        return self.functions.get(name)

    # -----------------------
    # VARIABLES (FIXED)
    # -----------------------
    def register_var(self, name, func=None):
        if func is None:
            def wrapper(f):
                self.vars[name] = f
                return f
            return wrapper

        self.vars[name] = func
        return func

    def get_var(self, name):
        return self.vars.get(name)


registry = FunctionRegistry()


# =========================================================
# VARIABLES IMPLEMENTATION
# =========================================================

@registry.register_var("server")
def server_var(ctx, args):
    g = ctx.guild
    arg = (args or "").strip().lower()

    if arg == "" or arg == "name":
        return g.name

    if arg == "boost":
        return g.premium_subscription_count or 0

    if arg == "boostlvl":
        return g.premium_tier

    return g.name


@registry.register_var("membercount")
def membercount_var(ctx, args):
    g = ctx.guild
    arg = (args or "").strip().lower()

    if arg in ("", "all"):
        return g.member_count

    if arg == "user":
        return sum(1 for m in g.members if not m.bot)

    if arg == "bots":
        return sum(1 for m in g.members if m.bot)

    return g.member_count

@registry.register_var("id")
def id_var(ctx, args):
    m = ctx.message.author
    arg = (args or "").strip().lower()

    if arg in ("", "user"):
        return str(m.id)

    if arg == "mention":
        return str(m.id)

    if arg == "act":
        return str(m.id)

    return str(m.id)

@registry.register_var("image")
def image_var(ctx, args):
    m = ctx.message.author
    arg = (args or "").strip().lower()

    if arg in ("", "user"):
        return m.display_avatar.url

    if arg == "mention":
        return m.display_avatar.url

    if arg == "act":
        return m.display_avatar.url

    return m.display_avatar.url

from datetime import datetime

@registry.register_var("time")
def time_var(ctx, args):
    now = datetime.utcnow()
    arg = (args or "").strip().lower()

    if arg in ("", "12h"):
        return now.strftime("%I:%M %p")

    if arg == "24h":
        return now.strftime("%H:%M")

    if arg == "nodate":
        return now.strftime("%H:%M:%S")

    if arg == "nodate;24h":
        return now.strftime("%H:%M:%S")

    return now.strftime("%H:%M:%S")
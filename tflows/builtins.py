"""Core built-in functions and variables that ship with every tflows bot.

Unlike the feature modules under :mod:`tflows.function`, built-ins are
registered by :func:`tflows.loader.load_function` through ``setup(registry)``
alongside the feature modules.
"""


def setup(registry):

    @registry.register("log")
    async def log(ctx, args):
        """Print a message to the bot's console for debugging."""
        print(f"[tflow log] {args}")

    @registry.register_var("prefix")
    def prefix_var(ctx, args):
        """Resolve ``$prefix`` to the bot's command prefix."""
        bot = getattr(ctx, "bot", None)
        prefix = getattr(bot, "command_prefix", "!")
        if isinstance(prefix, (list, tuple)):
            return prefix[0] if prefix else "!"
        if callable(prefix):
            return "!"
        return prefix

    @registry.register_var("command")
    def command_var(ctx, args):
        """Resolve ``$command`` to the currently running script command name."""
        return getattr(ctx, "command_name", "") or ""

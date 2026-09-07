"""Core built-in functions and variables that ship with every tflows bot.

Unlike the feature modules under :mod:`tflows.function`, built-ins are
registered by :func:`tflows.loader.load_function` through ``setup(registry)``
alongside the feature modules.
"""

from .runtime import access_path, stringify


def _extra(ctx, name, args=""):
    extras = getattr(ctx, "extras", None) or {}
    if name not in extras:
        lowered = name.lower()
        value = None
        for key, item in extras.items():
            if str(key).lower() == lowered:
                value = item
                break
    else:
        value = extras[name]
    if value is None:
        return ""
    if args:
        return stringify(access_path(value, args))
    return stringify(value)


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

    def _message_var(ctx, args):
        extras = getattr(ctx, "extras", None) or {}
        message = extras.get("message") or getattr(ctx, "message", None)
        if message is None:
            return ""
        arg = (args or "").strip().lower()
        if arg in ("", "content"):
            return str(getattr(message, "content", extras.get("content", "")) or "")
        if arg == "id":
            return str(getattr(message, "id", "") or "")
        if arg == "author":
            author = getattr(message, "author", None)
            return str(getattr(author, "name", author) or "")
        return stringify(access_path(message, args))

    registry.register_var("message", _message_var)

    @registry.register_var("emoji")
    def emoji_var(ctx, args):
        return _extra(ctx, "emoji", args)

    @registry.register_var("value")
    def value_var(ctx, args):
        extras = getattr(ctx, "extras", None) or {}
        if "value" in extras:
            return stringify(extras["value"])
        local = ctx.get_local("value") if hasattr(ctx, "get_local") else None
        if local is not None:
            return stringify(local)
        return ""

    @registry.register_var("interaction")
    def interaction_var(ctx, args):
        interaction = getattr(ctx, "interaction", None)
        if interaction is None:
            extras = getattr(ctx, "extras", None) or {}
            interaction = extras.get("interaction")
        if not interaction:
            return ""
        arg = (args or "").strip().lower()
        if arg in ("", "id"):
            return str(getattr(interaction, "id", "") or "")
        if arg == "user":
            user = getattr(interaction, "user", None)
            return str(getattr(user, "name", user) or "")
        return stringify(access_path(interaction, args))

    @registry.register_var("target")
    def target_var(ctx, args):
        extras = getattr(ctx, "extras", None) or {}
        target = extras.get("target")
        if target is None:
            return ""
        arg = (args or "").strip().lower()
        if not arg:
            return stringify(target)
        return stringify(access_path(target, args))

    @registry.register_var("content")
    def content_var(ctx, args):
        extras = getattr(ctx, "extras", None) or {}
        if "content" in extras:
            return stringify(extras["content"])
        return str(getattr(getattr(ctx, "message", None), "content", "") or "")

    @registry.register_var("input")
    def input_var(ctx, args):
        extras = getattr(ctx, "extras", None) or {}
        inputs = extras.get("input") or extras.get("inputs") or {}
        arg = (args or "").strip()
        if not arg:
            if isinstance(inputs, dict) and inputs:
                return stringify(next(iter(inputs.values())))
            return stringify(inputs)
        if isinstance(inputs, dict):
            if arg in inputs:
                return stringify(inputs[arg])
            lowered = arg.lower()
            for key, value in inputs.items():
                if str(key).lower() == lowered:
                    return stringify(value)
        return stringify(access_path(inputs, args))

    @registry.register("show_modal")
    async def show_modal(ctx, args):
        custom_id = (args or "").strip().strip("'\"")
        bot = getattr(ctx, "bot", None)
        spec = None
        if bot is not None:
            spec = getattr(bot, "modals", {}).get(custom_id)
        spec = spec or getattr(ctx, "pending_modal", None)
        interaction = getattr(ctx, "interaction", None)
        if interaction is None or spec is None:
            return
        try:
            import discord

            modal = discord.ui.Modal(
                title=str(spec.fields.get("title", "Modal"))[:45],
                custom_id=spec.fields.get("custom_id"),
            )
            for field in spec.fields.get("inputs") or []:
                modal.add_item(
                    discord.ui.TextInput(
                        label=str(field.get("label") or field.get("name") or "input")[:45],
                        custom_id=str(field.get("name") or "input")[:100],
                        placeholder=str(field.get("placeholder") or "")[:100],
                        required=bool(field.get("required", True)),
                    )
                )
            await interaction.response.send_modal(modal)
        except Exception:
            pass

    @registry.register("ephemeral")
    async def ephemeral_fn(ctx, args):
        flag = (args or "true").strip().lower()
        ctx.ephemeral = flag not in ("false", "no", "0", "off")

    @registry.register("defer")
    async def defer_fn(ctx, args):
        ctx.deferred = True
        interaction = getattr(ctx, "interaction", None)
        if interaction is None:
            return
        ephemeral = "ephemeral" in (args or "").lower() or getattr(ctx, "ephemeral", False)
        try:
            await interaction.response.defer(ephemeral=ephemeral)
        except Exception:
            pass

"""Persistent state functions: ``set`` / ``get`` / ``del`` / ``incr``.

Syntax::

    set points 10          # store "10" under key "points"
    set points +5           # atomic increment by 5 (creates 5 when missing)
    set points -2           # atomic decrement
    get points              # send the stored value (with optional fallback)
    get points 0            # send the value, or "0" when unset
    del points              # forget the key
    incr points             # atomic +1
    incr points 3           # atomic +3

Keys are namespaced per server automatically. Because ``$variables`` are
resolved before functions run, dynamic keys work naturally::

    set points[$user] +10
    get points[$user]

Inline reads: ``$get(points)`` or ``$get(points, 0)``.
"""

import re

_INCR_RE = re.compile(r"^[+-]\d+(?:\.\d+)?$")


def _store(ctx):
    bot = getattr(ctx, "bot", None)
    store = getattr(bot, "state", None) if bot is not None else None
    if store is None:
        raise RuntimeError(
            "persistent state is not enabled: pass state_path=... to FlowBot "
            "(e.g. FlowBot(prefix='!', state_path='tflows.db'))"
        )
    return store


def _namespace(ctx) -> str:
    from ..state import guild_namespace

    return guild_namespace(ctx)


def setup(registry):
    @registry.register("set")
    async def set_value(ctx, args):
        """Store ``set <key> <value...>``; ``+N``/``-N`` increments."""
        parts = (args or "").split(None, 1)
        if not parts:
            return
        key = parts[0]
        value = parts[1] if len(parts) > 1 else ""
        store = _store(ctx)
        namespace = _namespace(ctx)
        if _INCR_RE.match(value.strip()):
            delta = float(value.strip())
            await store.incr(namespace, key, int(delta) if delta.is_integer() else delta)
        else:
            await store.set(namespace, key, value)

    @registry.register("get")
    async def get_value(ctx, args):
        """Send ``get <key> [fallback...]`` to the channel."""
        parts = (args or "").split(None, 1)
        if not parts:
            return
        key = parts[0]
        fallback = parts[1] if len(parts) > 1 else None
        store = _store(ctx)
        value = await store.get(_namespace(ctx), key, default=fallback)
        if value is None or (isinstance(value, str) and not value):
            return
        await ctx.channel.send(str(value))

    @registry.register("del")
    async def del_value(ctx, args):
        """Forget ``del <key>``."""
        parts = (args or "").split(None, 1)
        if not parts:
            return
        await _store(ctx).delete(_namespace(ctx), parts[0])

    @registry.register("incr")
    async def incr_value(ctx, args):
        """Atomically increment ``incr <key> [amount]`` (default 1)."""
        parts = (args or "").split()
        if not parts:
            return
        try:
            delta = float(parts[1]) if len(parts) > 1 else 1
        except ValueError:
            delta = 1
        await _store(ctx).incr(
            _namespace(ctx), parts[0], int(delta) if float(delta).is_integer() else delta
        )

    @registry.register_var("get")
    async def get_var(ctx, args):
        """Inline read ``$get(key)`` / ``$get(key, fallback)``."""
        parts = [p.strip() for p in (args or "").split(",", 1)]
        if not parts or not parts[0]:
            return ""
        fallback = parts[1] if len(parts) > 1 else ""
        try:
            value = await _store(ctx).get(_namespace(ctx), parts[0], default=fallback)
        except RuntimeError:
            return fallback
        return "" if value is None else str(value)

    registry.register_var_alias("state", "get")

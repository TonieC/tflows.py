import logging

from ..context import record_error
from ..runtime import FlowValue, as_list
from ..utils import resolve_channel, resolve_user

logger = logging.getLogger("tflows.send")


def _send_kwargs(ctx):
    kwargs = {}
    view = None
    try:
        from ..components import build_view

        view = build_view(ctx)
    except Exception:
        view = getattr(ctx, "pending_view", None)
    if view is not None:
        kwargs["view"] = view
    if getattr(ctx, "ephemeral", False):
        kwargs["ephemeral"] = True
    return kwargs


def expand_recipients(value):
    """Turn a dm recipient value into a list of users / ids.

    Numeric ids and snowflake strings are kept whole (never iterated
    character-by-character). Nested lists/collections are flattened.
    """
    if isinstance(value, FlowValue):
        return expand_recipients(value.value)
    if value is None or value == "":
        return []
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [value]
    if isinstance(value, (bytes, bytearray)):
        return [value.decode("utf-8", "replace")]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.isdigit():
            return [text]
        if "," in text or "\n" in text:
            return as_list(text)
        return [text]
    if isinstance(value, dict):
        return expand_recipients(list(value.values()))
    if isinstance(value, (list, tuple, set)):
        out = []
        for item in value:
            out.extend(expand_recipients(item))
        return out
    if not isinstance(value, (str, bytes)) and (
        callable(getattr(value, "send", None))
        or callable(getattr(value, "create_dm", None))
        or (hasattr(value, "id") and hasattr(value, "name"))
    ):
        return [value]
    try:
        return [value]
    except Exception:
        return []


async def send_dm(ctx, recipient, text):
    """Send ``text`` as a DM to one or more recipients. Failures are logged."""
    bot = getattr(ctx, "bot", None)
    targets = expand_recipients(recipient)
    if not targets:
        msg = "dm: missing or invalid recipient"
        logger.warning("[tflow] %s", msg)
        record_error(ctx, msg)
        return
    text = "" if text is None else str(text)
    for item in targets:
        user, err = await resolve_user(bot, item)
        if user is None:
            msg = err or f"dm: invalid recipient: {item}"
            logger.warning("[tflow] %s", msg)
            record_error(ctx, msg)
            continue
        try:
            sender = getattr(user, "send", None)
            if callable(sender):
                await sender(text)
                continue
            create_dm = getattr(user, "create_dm", None)
            if callable(create_dm):
                dm = create_dm()
                if hasattr(dm, "__await__"):
                    dm = await dm
                await dm.send(text)
                continue
            msg = f"dm: recipient {getattr(user, 'id', item)} cannot receive DMs"
            logger.warning("[tflow] %s", msg)
            record_error(ctx, msg)
        except Exception as exc:
            msg = f"failed to DM {getattr(user, 'id', item)}: {exc}"
            logger.exception("[tflow] %s", msg)
            record_error(ctx, msg)


def setup(registry):

    @registry.register("send")
    async def send(ctx, args):
        kwargs = _send_kwargs(ctx)
        if args or kwargs:
            await ctx.channel.send(args if args else None, **kwargs)

    @registry.register("sendto")
    async def sendto(ctx, args):
        raw = (args or "").strip()
        if not raw:
            msg = "sendto: missing channel id"
            logger.warning("[tflow] %s", msg)
            record_error(ctx, msg)
            return
        parts = raw.split(None, 1)
        channel_id = parts[0]
        text = parts[1] if len(parts) > 1 else ""
        bot = getattr(ctx, "bot", None)
        channel, err = await resolve_channel(bot, channel_id)
        if channel is None:
            msg = err or f"sendto: channel not found: {channel_id}"
            logger.warning("[tflow] %s", msg)
            record_error(ctx, msg)
            return
        kwargs = _send_kwargs(ctx)
        try:
            if text or kwargs:
                await channel.send(text if text else None, **kwargs)
        except Exception as exc:
            msg = f"failed to send to channel {channel_id}: {exc}"
            logger.exception("[tflow] %s", msg)
            record_error(ctx, msg)

    @registry.register("dm")
    async def dm_fn(ctx, args):
        raw = (args or "").strip()
        if not raw:
            msg = "dm: missing recipient"
            logger.warning("[tflow] %s", msg)
            record_error(ctx, msg)
            return
        parts = raw.split(None, 1)
        await send_dm(ctx, parts[0], parts[1] if len(parts) > 1 else "")

    registry.register_alias("$dm", "dm")

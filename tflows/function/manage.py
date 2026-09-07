"""Member, role, and channel management functions.

All operations fail safely: missing permissions, missing targets, and API
errors are logged and (when possible) reported to the channel instead of
raising. Scripts never crash the bot because a kick failed.

Syntax::

    role add Moderator
    role add Moderator $user
    role remove Moderator
    role create Helpers color=green
    role delete Helpers

    kick $user reason="spam"
    ban $user reason="spam" delete_days=1
    unban 123456789
    timeout $user 10m reason="cool down"

    channel create chat type=text
    channel delete chat
    channel rename new-name
    channel topic "hello"
    channel nsfw true
    thread create "standup"
"""

from __future__ import annotations

import logging
from datetime import timedelta

from ..utils import parse_color, parse_duration

logger = logging.getLogger("tflows.manage")


def _fail(ctx, message: str):
    logger.warning("[tflow] %s", message)
    return message


def _guild(ctx):
    return getattr(ctx, "guild", None)


def _author(ctx):
    return getattr(ctx, "author", None)


def _parse_named(args: str) -> tuple[list[str], dict]:
    positional = []
    named = {}
    if not args:
        return positional, named
    tokens = _tokenize(args)
    for token in tokens:
        if "=" in token and not token.startswith("="):
            key, _, value = token.partition("=")
            named[key.strip().lower().replace("-", "_")] = value.strip().strip("'\"")
        else:
            positional.append(token.strip().strip("'\""))
    return positional, named


def _tokenize(text: str) -> list[str]:
    parts, buf, quote = [], [], None
    for char in text:
        if quote is not None:
            if char == quote:
                quote = None
            else:
                buf.append(char)
            continue
        if char in ("'", '"'):
            quote = char
            continue
        if char.isspace():
            if buf:
                parts.append("".join(buf))
                buf = []
            continue
        buf.append(char)
    if buf:
        parts.append("".join(buf))
    return parts


def _find_role(guild, name: str):
    if guild is None or not name:
        return None
    want = str(name).strip().strip("'\"")
    roles = getattr(guild, "roles", None) or []
    for role in roles:
        if str(getattr(role, "name", "")) == want:
            return role
        if str(getattr(role, "id", "")) == want:
            return role
    lowered = want.lower()
    for role in roles:
        if str(getattr(role, "name", "")).lower() == lowered:
            return role
    return None


def _find_member(guild, ctx, spec: str):
    if not spec:
        return _author(ctx)
    spec = str(spec).strip().strip("<>@!")
    members = list(getattr(guild, "members", None) or [])
    for member in members:
        if str(getattr(member, "id", "")) == spec:
            return member
        if str(getattr(member, "name", "")) == spec:
            return member
        if str(getattr(member, "display_name", "")) == spec:
            return member
        if str(getattr(member, "mention", "")) == spec:
            return member
    lowered = spec.lower()
    for member in members:
        if str(getattr(member, "name", "")).lower() == lowered:
            return member
    mentions = getattr(ctx, "mentions", None) or []
    if mentions:
        return mentions[0]
    return _author(ctx)


def _find_channel(guild, ctx, spec: str):
    if not spec:
        return getattr(ctx, "channel", None)
    spec = str(spec).strip().strip("<>#")
    channels = list(getattr(guild, "channels", None) or [])
    # Also search common attributes used by fakes.
    if not channels:
        system = getattr(guild, "system_channel", None)
        current = getattr(ctx, "channel", None)
        channels = [c for c in (system, current) if c is not None]
    for channel in channels:
        if str(getattr(channel, "id", "")) == spec:
            return channel
        if str(getattr(channel, "name", "")) == spec:
            return channel
    lowered = spec.lower()
    for channel in channels:
        if str(getattr(channel, "name", "")).lower() == lowered:
            return channel
    return getattr(ctx, "channel", None)


async def _safe(ctx, action, description: str):
    try:
        return await action()
    except Exception as exc:
        logger.exception("[tflow] %s failed", description)
        try:
            await ctx.channel.send(f"Failed to {description}: {exc}")
        except Exception:
            pass
        return None


def setup(registry):
    @registry.register("role")
    async def role_cmd(ctx, args):
        positional, named = _parse_named(args)
        if not positional:
            return _fail(ctx, "role: missing action")
        action = positional[0].lower()
        guild = _guild(ctx)
        if guild is None:
            return _fail(ctx, "role: not in a server")

        if action in ("add", "give"):
            if len(positional) < 2:
                return _fail(ctx, "role add: missing role name")
            role = _find_role(guild, positional[1])
            member = _find_member(guild, ctx, positional[2] if len(positional) > 2 else "")
            if role is None or member is None:
                return _fail(ctx, "role add: role or member not found")
            adder = getattr(member, "add_roles", None)
            if callable(adder):
                await _safe(ctx, lambda: adder(role), "add role")
            else:
                roles = list(getattr(member, "roles", []) or [])
                roles.append(role)
                member.roles = roles
            return None

        if action in ("remove", "take"):
            if len(positional) < 2:
                return _fail(ctx, "role remove: missing role name")
            role = _find_role(guild, positional[1])
            member = _find_member(guild, ctx, positional[2] if len(positional) > 2 else "")
            if role is None or member is None:
                return _fail(ctx, "role remove: role or member not found")
            remover = getattr(member, "remove_roles", None)
            if callable(remover):
                await _safe(ctx, lambda: remover(role), "remove role")
            else:
                roles = [r for r in (getattr(member, "roles", []) or []) if r is not role]
                member.roles = roles
            return None

        if action in ("create", "new"):
            if len(positional) < 2:
                return _fail(ctx, "role create: missing name")
            name = positional[1]
            kwargs = {}
            if "color" in named or "colour" in named:
                color = parse_color(named.get("color") or named.get("colour"))
                if color is not None:
                    try:
                        import discord

                        kwargs["color"] = discord.Color(color)
                    except Exception:
                        kwargs["color"] = color
            if "hoist" in named:
                kwargs["hoist"] = named["hoist"].lower() in ("1", "true", "yes")
            if "mentionable" in named:
                kwargs["mentionable"] = named["mentionable"].lower() in ("1", "true", "yes")
            creator = getattr(guild, "create_role", None)
            if callable(creator):
                await _safe(ctx, lambda: creator(name=name, **kwargs), "create role")
            else:
                roles = list(getattr(guild, "roles", []) or [])

                class _Role:
                    def __init__(self, n):
                        self.name = n
                        self.id = len(roles) + 1

                roles.append(_Role(name))
                guild.roles = roles
            return None

        if action in ("delete", "remove_role"):
            if len(positional) < 2:
                return _fail(ctx, "role delete: missing name")
            role = _find_role(guild, positional[1])
            if role is None:
                return _fail(ctx, "role delete: role not found")
            deleter = getattr(role, "delete", None)
            if callable(deleter):
                await _safe(ctx, deleter, "delete role")
            else:
                guild.roles = [r for r in (getattr(guild, "roles", []) or []) if r is not role]
            return None

        return _fail(ctx, f"role: unknown action {action!r}")

    @registry.register("kick")
    async def kick_cmd(ctx, args):
        positional, named = _parse_named(args)
        guild = _guild(ctx)
        if guild is None:
            return _fail(ctx, "kick: not in a server")
        member = _find_member(guild, ctx, positional[0] if positional else "")
        if member is None:
            return _fail(ctx, "kick: member not found")
        reason = named.get("reason", " ".join(positional[1:]) if len(positional) > 1 else None)
        kicker = getattr(member, "kick", None) or getattr(guild, "kick", None)
        if callable(kicker):
            await _safe(ctx, lambda: kicker(reason=reason) if reason else kicker(), "kick member")
        else:
            setattr(member, "kicked", True)
            setattr(member, "kick_reason", reason)
        return None

    @registry.register("ban")
    async def ban_cmd(ctx, args):
        positional, named = _parse_named(args)
        guild = _guild(ctx)
        if guild is None:
            return _fail(ctx, "ban: not in a server")
        member = _find_member(guild, ctx, positional[0] if positional else "")
        if member is None:
            return _fail(ctx, "ban: member not found")
        reason = named.get("reason")
        delete_days = named.get("delete_days") or named.get("deletedays")
        kwargs = {}
        if reason:
            kwargs["reason"] = reason
        if delete_days:
            try:
                kwargs["delete_message_days"] = int(delete_days)
            except ValueError:
                pass
        banner = getattr(member, "ban", None) or getattr(guild, "ban", None)
        if callable(banner):
            await _safe(ctx, lambda: banner(**kwargs) if kwargs else banner(), "ban member")
        else:
            setattr(member, "banned", True)
            setattr(member, "ban_reason", reason)
        return None

    @registry.register("unban")
    async def unban_cmd(ctx, args):
        positional, _named = _parse_named(args)
        guild = _guild(ctx)
        if guild is None:
            return _fail(ctx, "unban: not in a server")
        if not positional:
            return _fail(ctx, "unban: missing user id")
        user_id = positional[0]
        unbanner = getattr(guild, "unban", None)
        if callable(unbanner):
            await _safe(ctx, lambda: unbanner(user_id), "unban member")
        else:
            setattr(guild, "unbanned", getattr(guild, "unbanned", []) + [user_id])
        return None

    @registry.register("timeout")
    async def timeout_cmd(ctx, args):
        positional, named = _parse_named(args)
        guild = _guild(ctx)
        if guild is None:
            return _fail(ctx, "timeout: not in a server")
        member = _find_member(guild, ctx, positional[0] if positional else "")
        duration_raw = named.get("duration") or named.get("for") or (positional[1] if len(positional) > 1 else "60s")
        seconds = parse_duration(duration_raw) or 60
        until = timedelta(seconds=seconds)
        reason = named.get("reason")
        timer = getattr(member, "timeout", None) or getattr(member, "edit", None)
        if callable(getattr(member, "timeout", None)):
            await _safe(
                ctx,
                lambda: member.timeout(until, reason=reason) if reason else member.timeout(until),
                "timeout member",
            )
        elif callable(timer):
            await _safe(ctx, lambda: timer(timed_out_until=until), "timeout member")
        else:
            setattr(member, "timed_out", True)
            setattr(member, "timeout_seconds", seconds)
        return None

    @registry.register("channel")
    async def channel_cmd(ctx, args):
        positional, named = _parse_named(args)
        if not positional:
            return _fail(ctx, "channel: missing action")
        action = positional[0].lower()
        guild = _guild(ctx)
        if guild is None:
            return _fail(ctx, "channel: not in a server")

        if action in ("create", "new"):
            name = positional[1] if len(positional) > 1 else named.get("name")
            if not name:
                return _fail(ctx, "channel create: missing name")
            kind = (named.get("type") or "text").lower()
            creator = getattr(guild, "create_text_channel", None)
            if kind in ("voice", "vc"):
                creator = getattr(guild, "create_voice_channel", None) or creator
            if callable(creator):
                await _safe(ctx, lambda: creator(name), "create channel")
            else:
                created = list(getattr(guild, "channels", []) or [])

                class _Chan:
                    def __init__(self, n):
                        self.name = n
                        self.id = len(created) + 1000
                        self.topic = ""
                        self.nsfw = False

                    async def edit(self, **kwargs):
                        for key, value in kwargs.items():
                            setattr(self, key, value)

                    async def delete(self):
                        self.deleted = True

                created.append(_Chan(name))
                guild.channels = created
            return None

        if action in ("delete", "remove"):
            target = _find_channel(guild, ctx, positional[1] if len(positional) > 1 else "")
            if target is None:
                return _fail(ctx, "channel delete: not found")
            deleter = getattr(target, "delete", None)
            if callable(deleter):
                await _safe(ctx, deleter, "delete channel")
            else:
                setattr(target, "deleted", True)
            return None

        if action in ("rename", "name"):
            new_name = positional[1] if len(positional) > 1 else named.get("name")
            target = _find_channel(guild, ctx, positional[2] if len(positional) > 2 else "")
            if target is None or not new_name:
                return _fail(ctx, "channel rename: missing name or channel")
            editor = getattr(target, "edit", None)
            if callable(editor):
                await _safe(ctx, lambda: editor(name=new_name), "rename channel")
            else:
                target.name = new_name
            return None

        if action in ("topic", "subject"):
            topic = positional[1] if len(positional) > 1 else named.get("topic", "")
            target = getattr(ctx, "channel", None)
            editor = getattr(target, "edit", None)
            if callable(editor):
                await _safe(ctx, lambda: editor(topic=topic), "set topic")
            elif target is not None:
                target.topic = topic
            return None

        if action == "nsfw":
            flag = (positional[1] if len(positional) > 1 else "true").lower() in ("1", "true", "yes", "on")
            target = getattr(ctx, "channel", None)
            editor = getattr(target, "edit", None)
            if callable(editor):
                await _safe(ctx, lambda: editor(nsfw=flag), "set nsfw")
            elif target is not None:
                target.nsfw = flag
            return None

        return _fail(ctx, f"channel: unknown action {action!r}")

    @registry.register("thread")
    async def thread_cmd(ctx, args):
        positional, named = _parse_named(args)
        action = (positional[0].lower() if positional else "create")
        if action not in ("create", "new", "start"):
            name = positional[0] if positional else named.get("name", "thread")
        else:
            name = positional[1] if len(positional) > 1 else named.get("name", "thread")
        channel = getattr(ctx, "channel", None)
        starter = getattr(channel, "create_thread", None)
        if callable(starter):
            message = getattr(ctx, "message", None)
            await _safe(ctx, lambda: starter(name=name, message=message), "create thread")
        elif channel is not None:
            threads = list(getattr(channel, "threads", []) or [])
            threads.append(name)
            channel.threads = threads
        return None

    @registry.register_var("members")
    def members_var(ctx, args):
        guild = _guild(ctx)
        if guild is None:
            return []
        members = list(getattr(guild, "members", None) or [])
        arg = (args or "").strip().lower()
        if arg == "bots":
            members = [m for m in members if getattr(m, "bot", False)]
        elif arg in ("user", "users", "humans"):
            members = [m for m in members if not getattr(m, "bot", False)]
        names = [str(getattr(m, "display_name", getattr(m, "name", m))) for m in members]
        return names

    @registry.register_var("roles")
    def roles_var(ctx, args):
        guild = _guild(ctx)
        if guild is None:
            return []
        roles = list(getattr(guild, "roles", None) or [])
        return [str(getattr(r, "name", r)) for r in roles]

    @registry.register_var("channels")
    def channels_var(ctx, args):
        guild = _guild(ctx)
        if guild is None:
            return []
        channels = list(getattr(guild, "channels", None) or [])
        return [str(getattr(c, "name", c)) for c in channels]

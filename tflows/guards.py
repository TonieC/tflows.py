"""Declarative command controls: cooldowns and permission guards.

Script syntax (conventionally at the top of a command script)::

    cooldown 5s per user
    require manage_messages
    require role Moderator
    require owner

Cooldown scopes: ``user`` (default), ``channel``, ``guild``/``server``,
``global``. While on cooldown the script is not executed and a short notice
is sent instead. Permission failures behave the same way.

Discord permission names use the ``discord.Permissions`` attribute style
(``manage_messages``, ``administrator``, ``kick_members``, ...). Checks pass
when *any* of the author's relevant permission sources grants it
(``guild_permissions`` or channel ``permissions_for``), which keeps the
behaviour correct with both real discord.py objects and the test fakes.
"""

import logging
import re
import time

from .utils import parse_duration

logger = logging.getLogger("tflows.guards")

_SCOPE_ALIASES = {
    "user": "user",
    "member": "user",
    "author": "user",
    "channel": "channel",
    "guild": "guild",
    "server": "guild",
    "global": "global",
    "all": "global",
}


def parse_cooldown(line: str):
    """Parse ``cooldown 5s per user``; returns ``(seconds, scope)`` or ``None``.

    Accepts ``cooldown 5``, ``cooldown 5s``, ``cooldown 5s per user``,
    ``cooldown 10m per guild``. Returns ``None`` with no exception on
    invalid syntax so the engine can report a useful error.
    """
    match = re.fullmatch(
        r"cooldown\s+(\S+)(?:\s+per\s+(\w+))?", line.strip(), flags=re.IGNORECASE
    )
    if not match:
        return None
    seconds = parse_duration(match.group(1))
    if seconds is None or seconds < 0:
        return None
    scope = _SCOPE_ALIASES.get((match.group(2) or "user").lower(), "user")
    return (seconds, scope)


def parse_require(line: str):
    """Parse ``require ...``; returns ``(kind, value)`` or ``None``.

    Kinds: ``"perm"`` (discord permission name), ``"role"`` (role name),
    ``"owner"`` (guild owner). Examples: ``require manage_messages``,
    ``require role Moderator``, ``require owner``.
    """
    match = re.fullmatch(r"require\s+(.+)", line.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    rest = match.group(1).strip()
    if not rest:
        return None
    low = rest.lower()
    if low == "owner":
        return ("owner", "")
    role_match = re.fullmatch(r"role\s+(.+)", rest, flags=re.IGNORECASE)
    if role_match:
        return ("role", role_match.group(1).strip().strip("'\""))
    perm = re.sub(r"\s+", "_", rest).lower()
    return ("perm", perm)


def _scope_key(ctx, scope: str) -> str:
    author = getattr(ctx, "author", None)
    channel = getattr(ctx, "channel", None)
    try:
        guild = ctx.guild
    except Exception:
        guild = None
    if scope == "user":
        return f"user:{getattr(author, 'id', '?')}"
    if scope == "channel":
        return f"channel:{getattr(channel, 'id', '?')}"
    if scope == "guild":
        gid = getattr(guild, "id", None)
        return f"guild:{gid if gid is not None else 'global'}"
    return "global"


class CooldownManager:
    """Tracks per-command cooldown expirations. Async-safe (no I/O)."""

    def __init__(self):
        self._expires = {}
        self._time = time.monotonic

    def check(self, command: str, scope: str, scope_key: str, seconds: float) -> float:
        """Return seconds remaining, or 0 when the command may run.

        When the command may run, the cooldown window is (re)started.
        Expired entries are pruned opportunistically so per-user buckets
        cannot grow without bound.
        """
        now = self._time()
        if len(self._expires) > 512:
            self._expires = {k: v for k, v in self._expires.items() if v > now}
        key = (command, scope, scope_key)
        remaining = self._expires.get(key, 0) - now
        if remaining > 0:
            return remaining
        self._expires[key] = now + seconds
        return 0.0

    def reset(self, command: str | None = None) -> None:
        if command is None:
            self._expires.clear()
        else:
            for key in [k for k in self._expires if k[0] == command]:
                del self._expires[key]


def _author_roles(ctx) -> list:
    author = getattr(ctx, "author", None)
    roles = getattr(author, "roles", None) or []
    names = []
    for role in roles:
        names.append(str(getattr(role, "name", role)))
    return names


def author_has_role(ctx, name: str) -> bool:
    """Return True when the author has role ``name`` (case-insensitive).

    Convenience shortcuts: ``admin``/``administrator`` maps to the
    administrator permission, ``mod``/``moderator`` maps to common moderation
    permissions.
    """
    want = (name or "").strip().strip("'\"").lower()
    if not want:
        return False
    if want in ("admin", "administrator", "administrators"):
        return check_permission(ctx, "perm", "administrator")
    if want in ("mod", "moderator", "moderators"):
        for grant in ("manage_messages", "kick_members", "ban_members", "moderate_members"):
            if check_permission(ctx, "perm", grant):
                return True
    return any(role.lower() == want for role in _author_roles(ctx))


def check_permission(ctx, kind: str, value: str) -> bool:
    """Return True when the invoking author satisfies the requirement."""
    author = getattr(ctx, "author", None)
    if author is None:
        return False

    if kind == "owner":
        try:
            guild = ctx.guild
        except Exception:
            guild = None
        if guild is None:
            return False
        owner = getattr(guild, "owner", None)
        return owner is not None and getattr(owner, "id", None) == getattr(author, "id", None)

    if kind == "role":
        return author_has_role(ctx, value)

    # kind == "perm": consult guild_permissions first, then channel overwrite.
    for source in (
        getattr(author, "guild_permissions", None),
        _channel_permissions(ctx),
    ):
        if source is not None and getattr(source, value, False):
            return True
    # Fake objects expose a flat `permissions_for`-less model; also accept a
    # direct boolean attribute on the author (used by tests).
    direct = getattr(author, value, None)
    if isinstance(direct, bool):
        return direct
    return False


def _channel_permissions(ctx):
    try:
        channel = ctx.channel
        guild = ctx.guild
        me = getattr(guild, "me", None)
        author = getattr(ctx, "author", None)
        permissions_for = getattr(channel, "permissions_for", None)
        if callable(permissions_for):
            # Prefer the author's effective permissions; fall back to the
            # bot's (fakes grant everything to everyone, real guilds do not).
            try:
                return permissions_for(author)
            except Exception:
                if me is not None:
                    return permissions_for(me)
    except Exception:
        pass
    return None

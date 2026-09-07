"""Event triggers: run scripts when Discord events fire, no command needed.

Python API::

    bot.on_event("join", "send Welcome $user(mention)!")
    bot.on_event("react", "send $user(display) reacted!")
    bot.on_event("message", "send hi", where='channel == "general"')

Script-header style (accepted verbatim; the header is informational)::

    on join:
        send Welcome!

    on message where channel == "general":
        send hello

Minimum supported events: ``join`` (member join), ``leave`` (member
remove), ``react`` (reaction add). The :data:`EVENT_MAP` translates friendly
names to ``discord.py`` listener names, so new events are added by extending
the map — the scripting language itself never changes.
"""

import logging
import re

from .syntax import parse_on_where

logger = logging.getLogger("tflows.events")

# Friendly name -> discord.py Client event name. Extend this map to support
# more events without touching the scripting language.
EVENT_MAP = {
    "join": "on_member_join",
    "member_join": "on_member_join",
    "welcome": "on_member_join",
    "leave": "on_member_remove",
    "member_leave": "on_member_remove",
    "member_remove": "on_member_remove",
    "remove": "on_member_remove",
    "react": "on_reaction_add",
    "reaction": "on_reaction_add",
    "reaction_add": "on_reaction_add",
    "unreact": "on_reaction_remove",
    "reaction_remove": "on_reaction_remove",
    "message": "on_message_event",
    "typing": "on_typing",
    "button": "on_button",
    "select": "on_select",
    "modal": "on_modal",
    "interaction": "on_interaction",
}

_ON_HEADER_RE = re.compile(r"^on\s+([\w\s]+?)\s*:?\s*$", re.IGNORECASE)


def parse_on_header(line: str):
    """Return the event name for ``on join:`` lines, else ``None``.

    ``on message where ...`` is handled by :func:`parse_on_where` first.
    """
    stripped = line.strip()
    if parse_on_where(stripped) is not None:
        event, _cond = parse_on_where(stripped)
        return event
    match = _ON_HEADER_RE.match(stripped)
    if not match:
        return None
    name = match.group(1).strip().lower().replace(" ", "_")
    return name


def strip_event_header(code: str) -> str:
    """Remove a leading ``on <event>:`` / ``on <event> where ...:`` header."""
    lines = (code or "").split("\n")
    if not lines:
        return code or ""
    first = lines[0]
    if parse_on_where(first) is not None or parse_on_header(first) is not None:
        return "\n".join(lines[1:])
    return code or ""


def event_filter_from_code(code: str):
    """Return the ``where`` clause of a leading ``on ... where ...`` header."""
    lines = (code or "").split("\n")
    if not lines:
        return None
    parsed = parse_on_where(lines[0].strip())
    if parsed is None:
        return None
    return parsed[1]


def normalize_event(name: str) -> str:
    """Map a friendly event name to its discord.py listener name."""
    key = (name or "").strip().lower().replace(" ", "_")
    if key in EVENT_MAP:
        return EVENT_MAP[key]
    valid = sorted(set(EVENT_MAP))
    raise ValueError(f"unknown event {name!r}. Supported events: {', '.join(valid)}")


class EventRegistry:
    """Stores ``listener -> [(handle_name, code, channel, where)]`` handlers."""

    def __init__(self):
        self.handlers: dict = {}

    def add(self, event: str, code: str, name: str | None = None, channel=None, where: str | None = None) -> str:
        listener = normalize_event(event)
        extracted = event_filter_from_code(code)
        if where is None:
            where = extracted
        code = strip_event_header(code)
        handle_name = name or f"{event}_{len(self.handlers.get(listener, []))}"
        self.handlers.setdefault(listener, []).append((handle_name, code, channel, where))
        return handle_name

    def remove(self, event: str, name: str) -> bool:
        listener = normalize_event(event)
        entries = self.handlers.get(listener, [])
        for i, entry in enumerate(entries):
            if entry[0] == name:
                del entries[i]
                return True
        return False

    def get(self, listener: str) -> list:
        return list(self.handlers.get(listener, []))

    def clear(self) -> None:
        self.handlers.clear()

    @property
    def event_names(self) -> list:
        return sorted(self.handlers)


def _bare_filter_value(ctx, name: str):
    """Resolve a bare identifier used in an event ``where`` clause."""
    extras = getattr(ctx, "extras", None) or {}
    if name in extras:
        value = extras[name]
        from .runtime import stringify

        return stringify(value)
    lowered = name.lower()
    if lowered == "channel":
        channel = getattr(ctx, "channel", None)
        return str(getattr(channel, "name", "") or "")
    if lowered in ("user", "author", "member"):
        author = getattr(ctx, "author", None)
        return str(getattr(author, "display_name", getattr(author, "name", "")) or "")
    if lowered == "message":
        message = extras.get("message") or getattr(ctx, "message", None)
        return str(getattr(message, "content", extras.get("content", "")) or "")
    if lowered == "content":
        return str(extras.get("content", getattr(getattr(ctx, "message", None), "content", "") or ""))
    if lowered == "emoji":
        return str(extras.get("emoji", ""))
    if lowered == "value":
        return str(extras.get("value", ""))
    if lowered == "role":
        author = getattr(ctx, "author", None)
        roles = getattr(author, "roles", None) or []
        return ", ".join(str(getattr(r, "name", r)) for r in roles)
    return None


async def matches_filter(ctx, engine, where: str) -> bool:
    """Return True when the event context satisfies ``where``."""
    if not where or not str(where).strip():
        return True
    from .conditionals import evaluate_condition, evaluate_condition_text
    from .guards import author_has_role
    from .runtime import stringify

    expr = where.strip()
    # `role == "Member"` → member has that role.
    role_eq = re.match(r'^role\s*==\s*(.+)$', expr, re.IGNORECASE)
    if role_eq:
        want = role_eq.group(1).strip().strip("'\"")
        want = await engine.replace_vars(ctx, want)
        return author_has_role(ctx, want)

    resolved = await engine.replace_vars(ctx, expr)
    # Substitute bare identifiers (channel, user, message, ...) when they
    # sit outside quotes.
    quote = None
    out = []
    i = 0
    ident = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    while i < len(resolved):
        char = resolved[i]
        if quote is not None:
            out.append(char)
            if char == quote:
                quote = None
            i += 1
            continue
        if char in ("'", '"'):
            quote = char
            out.append(char)
            i += 1
            continue
        match = ident.match(resolved, i)
        if match:
            word = match.group(0)
            value = _bare_filter_value(ctx, word)
            if value is not None and word.lower() not in (
                "and",
                "or",
                "not",
                "contains",
                "startswith",
                "endswith",
                "in",
                "true",
                "false",
            ):
                text = stringify(value).replace('"', '\\"')
                out.append(f'"{text}"')
                i = match.end()
                continue
        out.append(char)
        i += 1
    rewritten = "".join(out)
    try:
        return evaluate_condition_text(rewritten)
    except Exception:
        try:
            return await evaluate_condition(ctx, engine, expr)
        except Exception:
            return False

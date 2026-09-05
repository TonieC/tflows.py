"""Event triggers: run scripts when Discord events fire, no command needed.

Python API::

    bot.on_event("join", "send Welcome $user(mention)!")
    bot.on_event("react", "send $user(display) reacted!")

Script-header style (accepted verbatim; the header is informational)::

    on join:
        send Welcome!

Minimum supported events: ``join`` (member join), ``leave`` (member
remove), ``react`` (reaction add). The :data:`EVENT_MAP` translates friendly
names to ``discord.py`` listener names, so new events are added by extending
the map — the scripting language itself never changes.
"""

import logging
import re

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
}

_ON_HEADER_RE = re.compile(r"^on\s+([\w\s]+?)\s*:?\s*$", re.IGNORECASE)


def parse_on_header(line: str):
    """Return the event name for ``on join:`` lines, else ``None``."""
    match = _ON_HEADER_RE.match(line.strip())
    if not match:
        return None
    return match.group(1).strip().lower().replace(" ", "_")


def strip_event_header(code: str) -> str:
    """Remove a leading ``on <event>:`` header so the body runs verbatim."""
    lines = (code or "").split("\n")
    if lines and parse_on_header(lines[0]):
        return "\n".join(lines[1:])
    return code or ""


def normalize_event(name: str) -> str:
    """Map a friendly event name to its discord.py listener name."""
    key = (name or "").strip().lower().replace(" ", "_")
    if key in EVENT_MAP:
        return EVENT_MAP[key]
    valid = sorted(set(EVENT_MAP))
    raise ValueError(f"unknown event {name!r}. Supported events: {', '.join(valid)}")


class EventRegistry:
    """Stores ``listener -> [(handle_name, code, channel)]`` script handlers."""

    def __init__(self):
        self.handlers: dict = {}

    def add(self, event: str, code: str, name: str | None = None, channel=None) -> str:
        listener = normalize_event(event)
        code = strip_event_header(code)
        handle_name = name or f"{event}_{len(self.handlers.get(listener, []))}"
        self.handlers.setdefault(listener, []).append((handle_name, code, channel))
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

    @property
    def event_names(self) -> list:
        return sorted(self.handlers)

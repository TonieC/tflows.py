"""Runtime values, control-flow signals, and script-defined functions.

The engine evaluates expressions to :class:`FlowValue` instances. Template
substitution (``$name``) always stringifies; loops and functions keep the
underlying Python value so lists, numbers and JSON objects round-trip.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


class FlowBreak(Exception):
    """Raised by the ``break`` statement to leave the innermost loop."""


class FlowContinue(Exception):
    """Raised by the ``continue`` statement to skip the rest of a loop body."""


class FlowReturn(Exception):
    """Raised by ``return`` to leave a function (or the whole script)."""

    def __init__(self, value: Any = ""):
        super().__init__(value)
        self.value = value


def stringify(value: Any) -> str:
    """Convert a runtime value to the string scripts send / interpolate."""
    if value is None:
        return ""
    if isinstance(value, FlowValue):
        return stringify(value.value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (list, tuple)):
        return ", ".join(stringify(item) for item in value)
    if isinstance(value, dict):
        try:
            return json.dumps(value, default=str)
        except TypeError:
            return str(value)
    return str(value)


def to_number(value: Any):
    """Best-effort numeric conversion; returns ``None`` when it is not a number."""
    if isinstance(value, FlowValue):
        return to_number(value.value)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        if "." in text or "e" in text.lower():
            return float(text)
        return int(text)
    except (TypeError, ValueError):
        return None


def is_truthy(value: Any) -> bool:
    if isinstance(value, FlowValue):
        return is_truthy(value.value)
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, (list, tuple, dict)):
        return len(value) > 0
    text = str(value).strip().lower()
    return text not in {"", "0", "false", "no", "none", "null", "nil", "[]", "{}"}


def as_list(value: Any) -> list:
    """Turn a value into an iterable list for ``for`` loops."""
    if isinstance(value, FlowValue):
        return as_list(value.value)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return list(value.items())
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if "\n" in text:
            return [line for line in text.split("\n") if line != ""]
        if "," in text:
            return [part.strip() for part in text.split(",") if part.strip()]
        return [text]
    try:
        return list(value)
    except TypeError:
        return [value]


class FlowValue:
    """A boxed script value (string, number, list, dict, or Discord object)."""

    __slots__ = ("value",)

    def __init__(self, value: Any = ""):
        if isinstance(value, FlowValue):
            self.value = value.value
        else:
            self.value = value

    def stringify(self) -> str:
        return stringify(self.value)

    def __str__(self) -> str:
        return stringify(self.value)

    def __repr__(self) -> str:
        return f"FlowValue({self.value!r})"

    def __bool__(self) -> bool:
        return is_truthy(self.value)

    def access(self, path: str):
        """Resolve ``.field`` / ``[key]`` / ``(option)`` against this value."""
        return access_path(self.value, path)


def access_path(value: Any, path: str):
    """Walk ``.field`` and ``[key]`` segments, plus a parenthesized option.

    ``$user(display)`` uses the option form (handled by variable resolvers).
    ``$data[name]`` and ``$message.content`` use this helper after the root
    value has been resolved.
    """
    if isinstance(value, FlowValue):
        value = value.value
    path = (path or "").strip()
    if not path:
        return value

    i = 0
    while i < len(path):
        char = path[i]
        if char == ".":
            i += 1
            start = i
            while i < len(path) and (path[i].isalnum() or path[i] == "_"):
                i += 1
            key = path[start:i]
            value = _get_field(value, key)
        elif char == "[":
            i += 1
            start = i
            depth = 1
            while i < len(path) and depth:
                if path[i] == "[":
                    depth += 1
                elif path[i] == "]":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            key = path[start:i].strip().strip("'\"")
            if i < len(path) and path[i] == "]":
                i += 1
            value = _get_field(value, key)
        elif char == "(":
            break
        else:
            i += 1
    return value


def _get_field(value: Any, key: str):
    if value is None:
        return ""
    if isinstance(value, FlowValue):
        value = value.value
    if isinstance(value, dict):
        if key in value:
            return value[key]
        lowered = key.lower()
        for candidate, item in value.items():
            if str(candidate).lower() == lowered:
                return item
        return ""
    if isinstance(value, (list, tuple)):
        try:
            index = int(key)
        except (TypeError, ValueError):
            return ""
        if 0 <= index < len(value):
            return value[index]
        if index < 0 and abs(index) <= len(value):
            return value[index]
        return ""
    # Discord / fake objects: attribute then mapping-style option.
    if hasattr(value, key):
        attr = getattr(value, key)
        return attr() if callable(attr) and not isinstance(attr, type) else attr
    # Common option aliases used by $user(display)-style resolvers.
    lowered = key.lower()
    mapping = {
        "name": lambda obj: getattr(obj, "name", obj),
        "display": lambda obj: getattr(obj, "display_name", getattr(obj, "name", obj)),
        "id": lambda obj: getattr(obj, "id", ""),
        "mention": lambda obj: getattr(obj, "mention", ""),
        "content": lambda obj: getattr(obj, "content", ""),
        "body": lambda obj: getattr(obj, "body", getattr(obj, "content", "")),
        "status": lambda obj: getattr(obj, "status", ""),
        "url": lambda obj: getattr(obj, "url", ""),
        "value": lambda obj: getattr(obj, "value", obj),
    }
    getter = mapping.get(lowered)
    if getter is not None:
        try:
            return getter(value)
        except Exception:
            return ""
    return ""


@dataclass
class ScriptFunction:
    """A function defined in a tflows script (not a Python builtin)."""

    name: str
    params: list[str]
    body: str
    source: str = ""
    filename: str = ""


@dataclass
class ScriptModule:
    """A loaded ``.flow`` file: functions plus any registered commands/events."""

    path: str
    functions: dict[str, ScriptFunction] = field(default_factory=dict)
    commands: list = field(default_factory=list)
    events: list = field(default_factory=list)
    schedules: list = field(default_factory=list)
    context_menus: list = field(default_factory=list)

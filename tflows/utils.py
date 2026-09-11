"""Shared helpers used across tflows.

Kept dependency-light: everything here works on plain Python values so the
helpers can be reused by tests and by third-party function modules.
"""

import random as _random
import re

# ---------------------------------------------------------------------------
# Named embed colors
# ---------------------------------------------------------------------------
COLORS = {
    "white": 0xFFFFFF,
    "black": 0x000000,
    "red": 0xE74C3C,
    "green": 0x2ECC71,
    "blue": 0x3498DB,
    "yellow": 0xF1C40F,
    "orange": 0xE67E22,
    "purple": 0x9B59B6,
    "pink": 0xE91E63,
    "grey": 0x95A5A6,
    "gray": 0x95A5A6,
    "blurple": 0x5865F2,
    "gold": 0xF1C40F,
    "teal": 0x1ABC9C,
    "cyan": 0x00BCD4,
    "brown": 0x8B5A2B,
}


def parse_color(value):
    """Convert a hex string or named color into an RGB integer.

    Returns ``None`` when the value cannot be parsed so callers can fall back
    to a default color instead of crashing.
    """
    if value is None:
        return None
    raw = str(value).strip().lower()
    raw = raw.replace("#", "").replace("0x", "")

    if not raw:
        return None

    if raw in COLORS:
        return COLORS[raw]

    try:
        return int(raw, 16)
    except ValueError:
        return None


_DURATION_UNITS = {
    "ms": 0.001,
    "msec": 0.001,
    "millis": 0.001,
    "millisecond": 0.001,
    "milliseconds": 0.001,
    "s": 1.0,
    "sec": 1.0,
    "secs": 1.0,
    "second": 1.0,
    "seconds": 1.0,
    "m": 60.0,
    "min": 60.0,
    "mins": 60.0,
    "minute": 60.0,
    "minutes": 60.0,
    "h": 3600.0,
    "hr": 3600.0,
    "hrs": 3600.0,
    "hour": 3600.0,
    "hours": 3600.0,
    "d": 86400.0,
    "day": 86400.0,
    "days": 86400.0,
    "w": 604800.0,
    "wk": 604800.0,
    "wks": 604800.0,
    "week": 604800.0,
    "weeks": 604800.0,
}

_UNIT_PATTERN = "|".join(sorted(_DURATION_UNITS, key=len, reverse=True))
_SEGMENT_RE = re.compile(rf"(\d+(?:\.\d+)?)\s*({_UNIT_PATTERN})?", re.IGNORECASE)


def parse_duration(value):
    """Parse a duration into seconds.

    Accepts numbers (seconds), compact units (``5s``, ``2m``, ``1h30m``,
    ``500ms``), mixed tokens (``1h 30m``, ``1 hour 30 minutes``), and
    word units (``seconds``, ``minutes``, ``hours``, ``days``, ``weeks``).

    Returns ``None`` when the value cannot be parsed.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().lower().replace(",", " ")
    if not raw:
        return None
    raw = re.sub(r"\s+", " ", raw)

    total = 0.0
    found = False
    pos = 0
    for match in _SEGMENT_RE.finditer(raw):
        gap = raw[pos : match.start()].strip()
        if gap not in ("", "and", "+", "&"):
            return None
        pos = match.end()
        number = float(match.group(1))
        unit = (match.group(2) or "").lower()
        if not unit:
            if found or raw[pos:].strip():
                return None
            return number
        total += number * _DURATION_UNITS[unit]
        found = True
    if not found:
        return None
    if raw[pos:].strip() not in ("", "and"):
        return None
    return total


def coerce_duration(value, default=None):
    """Parse ``value`` as seconds, falling back to ``default``."""
    parsed = parse_duration(value)
    if parsed is None:
        return default
    return parsed


def format_duration(seconds):
    """Format seconds as a compact mixed-unit string (``1h 30m``, ``500ms``)."""
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        return ""
    if value < 0:
        value = 0.0
    if value == 0:
        return "0s"
    millis = int(round(value * 1000))
    if millis < 1000:
        return f"{millis}ms"
    weeks, millis = divmod(millis, 604800000)
    days, millis = divmod(millis, 86400000)
    hours, millis = divmod(millis, 3600000)
    minutes, millis = divmod(millis, 60000)
    secs, millis = divmod(millis, 1000)
    parts = []
    if weeks:
        parts.append(f"{weeks}w")
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")
    if millis:
        parts.append(f"{millis}ms")
    return " ".join(parts) or "0s"


def random_int(start, end):
    """Return a random integer in the inclusive range ``[start, end]``.

    Handles reversed bounds gracefully (``random(5, 1)`` == ``random(1, 5)``).
    """
    try:
        a, b = int(start), int(end)
    except (TypeError, ValueError):
        return None
    if a > b:
        a, b = b, a
    return _random.randint(a, b)

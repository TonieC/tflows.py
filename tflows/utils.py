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


_DURATION_UNITS = {"s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}


def parse_duration(value):
    """Parse a duration such as ``5``, ``5s``, ``2m``, ``1h`` into seconds.

    Returns ``None`` when the value cannot be parsed.
    """
    if value is None:
        return None
    raw = str(value).strip().lower()
    if not raw:
        return None

    match = re.fullmatch(r"(\d+(?:\.\d+)?)([smhd]?)", raw)
    if not match:
        return None

    number = float(match.group(1))
    unit = match.group(2) or "s"
    return number * _DURATION_UNITS[unit]


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

"""Header parsers for tflows language constructs.

Kept separate from the interpreter so ``tflows check`` can reuse them
without executing scripts.
"""

from __future__ import annotations

import re

from .conditionals import is_else, is_endif, parse_if_header

_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"

_FOR_RE = re.compile(rf"^for\s+({_IDENT})\s+in\s+(.+?)\s*:?\s*$", re.IGNORECASE)
_REPEAT_RE = re.compile(r"^repeat\s+(.+?)\s*:?\s*$", re.IGNORECASE)
_FUNCTION_RE = re.compile(rf"^function\s+({_IDENT})\s*\((.*)\)\s*:?\s*$", re.IGNORECASE)
_FUNCTION_NOARGS_RE = re.compile(rf"^function\s+({_IDENT})\s*:?\s*$", re.IGNORECASE)
_IMPORT_RE = re.compile(r"^import\s+(.+?)\s*$", re.IGNORECASE)
_RETURN_RE = re.compile(r"^return(?:\s+(.*))?$", re.IGNORECASE)
_BUTTON_RE = re.compile(r"^button\s+(.+?)\s*:?\s*$", re.IGNORECASE)
_SELECT_RE = re.compile(r"^select\s+(.+?)\s*:?\s*$", re.IGNORECASE)
_OPTION_RE = re.compile(r"^option\s+(.+?)\s*$", re.IGNORECASE)
_MODAL_RE = re.compile(r"^modal\s+(.+?)\s*:?\s*$", re.IGNORECASE)
_INPUT_RE = re.compile(r"^input\s+(.+?)\s*$", re.IGNORECASE)
_CALL_RE = re.compile(rf"^({_IDENT})\s*\((.*)\)\s*$")
_ON_COMPONENT_RE = re.compile(
    r"^on\s+(button|select|modal)\s+(.+?)\s*:?\s*$", re.IGNORECASE
)
_ON_WHERE_RE = re.compile(
    r"^on\s+([\w\s]+?)\s+where\s+(.+?)\s*:?\s*$", re.IGNORECASE
)
_COMMAND_HEADER_RE = re.compile(rf"^command\s+({_IDENT})\s*:?\s*$", re.IGNORECASE)
_CONTEXT_MENU_RE = re.compile(
    r"^context(?:[_\s]menu)?\s+(user|message)\s+(.+?)\s*:?\s*$", re.IGNORECASE
)


def _strip_colon(text: str) -> str:
    text = text.strip()
    if text.endswith(":"):
        return text[:-1].strip()
    return text


def parse_kv_attrs(text: str) -> tuple[str, dict]:
    """Split ``"Label" id="hello" style="primary"`` into (positional, attrs)."""
    attrs = {}
    positional = []
    token_re = re.compile(
        r'([A-Za-z_]\w*)\s*=\s*("([^"]*)"|\'([^\']*)\'|\S+)|"([^"]*)"|\'([^\']*)\'|(\S+)'
    )
    for match in token_re.finditer(text.strip()):
        if match.group(1):
            key = match.group(1).lower()
            value = match.group(3) if match.group(3) is not None else (
                match.group(4) if match.group(4) is not None else match.group(2)
            )
            attrs[key] = value
        elif match.group(5) is not None:
            positional.append(match.group(5))
        elif match.group(6) is not None:
            positional.append(match.group(6))
        elif match.group(7) is not None:
            positional.append(match.group(7))
    return " ".join(positional), attrs


def parse_for_header(stripped: str):
    match = _FOR_RE.match(_strip_colon(stripped) if stripped.endswith(":") else stripped)
    if not match:
        # allow with colon still in string
        match = _FOR_RE.match(stripped)
    if not match:
        return None
    return match.group(1), match.group(2).rstrip(":").strip()


def parse_repeat_header(stripped: str):
    match = _REPEAT_RE.match(stripped)
    if not match:
        return None
    return match.group(1).rstrip(":").strip()


def parse_function_header(stripped: str):
    match = _FUNCTION_RE.match(stripped) or _FUNCTION_NOARGS_RE.match(stripped)
    if not match:
        return None
    name = match.group(1)
    raw_params = match.group(2) if match.lastindex >= 2 else ""
    params = [p.strip() for p in (raw_params or "").split(",") if p.strip()]
    return name, params


def parse_import(stripped: str):
    match = _IMPORT_RE.match(stripped)
    if not match:
        return None
    target = match.group(1).strip().strip("'\"")
    return target or None


def parse_return(stripped: str):
    match = _RETURN_RE.match(stripped)
    if not match:
        return None
    return (match.group(1) or "").strip()


def parse_button_header(stripped: str):
    if not stripped.lower().startswith("button"):
        return None
    rest = stripped[6:].strip()
    if rest.endswith(":"):
        rest = rest[:-1].strip()
    label, attrs = parse_kv_attrs(rest)
    if not label and "label" in attrs:
        label = attrs["label"]
    return label, attrs


def parse_select_header(stripped: str):
    if not stripped.lower().startswith("select"):
        return None
    if stripped.lower().startswith("selectmenu"):
        return None
    rest = stripped[6:].strip()
    if rest.endswith(":"):
        rest = rest[:-1].strip()
    # `select` alone or `select id="x"` — not `select` as in SQL.
    if rest.lower().startswith("in "):
        return None
    positional, attrs = parse_kv_attrs(rest)
    if positional and "id" not in attrs:
        attrs.setdefault("placeholder", positional)
    return attrs


def parse_option_line(stripped: str):
    match = _OPTION_RE.match(stripped)
    if not match:
        return None
    positional, attrs = parse_kv_attrs(match.group(1))
    label = positional or attrs.get("label", "")
    value = attrs.get("value", label)
    return label, value, attrs


def parse_modal_header(stripped: str):
    if not stripped.lower().startswith("modal"):
        return None
    rest = stripped[5:].strip()
    if rest.endswith(":"):
        rest = rest[:-1].strip()
    title, attrs = parse_kv_attrs(rest)
    if not title and "title" in attrs:
        title = attrs["title"]
    return title, attrs


def parse_input_line(stripped: str):
    match = _INPUT_RE.match(stripped)
    if not match:
        return None
    positional, attrs = parse_kv_attrs(match.group(1))
    name = attrs.get("id") or attrs.get("name") or positional.split()[0] if positional else ""
    label = attrs.get("label") or positional or name
    return name, label, attrs


def parse_call(stripped: str):
    """Parse ``name(arg, arg)`` script-function calls."""
    match = _CALL_RE.match(stripped)
    if not match:
        return None
    name = match.group(1)
    raw = match.group(2).strip()
    if not raw:
        return name, []
    args = _split_args(raw)
    return name, args


def _split_args(text: str) -> list:
    parts, buf, quote, depth = [], [], None, 0
    for char in text:
        if quote is not None:
            buf.append(char)
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            buf.append(char)
        elif char == "(":
            depth += 1
            buf.append(char)
        elif char == ")":
            depth = max(0, depth - 1)
            buf.append(char)
        elif char == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(char)
    if buf:
        parts.append("".join(buf).strip())
    return [p for p in parts if p]


split_call_args = _split_args


def parse_on_component(stripped: str):
    match = _ON_COMPONENT_RE.match(stripped)
    if not match:
        return None
    kind = match.group(1).lower()
    rest = match.group(2).rstrip(":").strip()
    positional, attrs = parse_kv_attrs(rest)
    custom_id = attrs.get("id") or positional.strip("'\"")
    return kind, custom_id


def parse_on_where(stripped: str):
    """Parse ``on message where channel == "general":``.

    Returns ``(event_name, condition)`` or ``None``.
    """
    match = _ON_WHERE_RE.match(stripped)
    if not match:
        return None
    event = match.group(1).strip().lower().replace(" ", "_")
    condition = match.group(2).rstrip(":").strip()
    return event, condition


def parse_command_header(stripped: str):
    match = _COMMAND_HEADER_RE.match(stripped)
    if not match:
        return None
    return match.group(1)


def parse_context_menu_header(stripped: str):
    match = _CONTEXT_MENU_RE.match(stripped)
    if not match:
        return None
    kind = match.group(1).lower()
    rest = match.group(2).rstrip(":").strip()
    positional, attrs = parse_kv_attrs(rest)
    name = positional.strip("'\"") or attrs.get("name", "")
    return kind, name, attrs


def is_break(stripped: str) -> bool:
    return stripped.lower().rstrip(":").strip() == "break"


def is_continue(stripped: str) -> bool:
    return stripped.lower().rstrip(":").strip() == "continue"


def is_endfor(stripped: str) -> bool:
    return stripped.lower().rstrip(":").strip() in ("endfor", "end for")


def is_endrepeat(stripped: str) -> bool:
    return stripped.lower().rstrip(":").strip() in ("endrepeat", "end repeat")


def is_endfunction(stripped: str) -> bool:
    return stripped.lower().rstrip(":").strip() in ("endfunction", "end function", "endfn")


def is_endbutton(stripped: str) -> bool:
    return stripped.lower().rstrip(":").strip() in ("endbutton", "end button")


def is_endselect(stripped: str) -> bool:
    return stripped.lower().rstrip(":").strip() in ("endselect", "end select")


def is_endmodal(stripped: str) -> bool:
    return stripped.lower().rstrip(":").strip() in ("endmodal", "end modal")


def is_block_ender(stripped: str) -> bool:
    return (
        is_endif(stripped)
        or is_else(stripped)
        or is_endfor(stripped)
        or is_endrepeat(stripped)
        or is_endfunction(stripped)
        or is_endbutton(stripped)
        or is_endselect(stripped)
        or is_endmodal(stripped)
        or (parse_if_header(stripped) is not None and parse_if_header(stripped)[0] == "elif")
    )


def is_defer(stripped: str) -> bool:
    low = stripped.lower()
    return low == "defer" or low.startswith("defer ")


def is_ephemeral(stripped: str) -> bool:
    return stripped.lower() in ("ephemeral", "ephemeral true", "ephemeral yes")


# Re-export so checkers have a single import surface.
parse_if_header = parse_if_header
is_else = is_else
is_endif = is_endif

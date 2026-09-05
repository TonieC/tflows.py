"""Lightweight conditionals for the tflows scripting language.

Supported script syntax::

    if $argcount > 1:
        reply "Multiple arguments"
    elif $argcount == 1:
        reply "One argument"
    else:
        reply "No arguments"
    endif

``endif`` is optional when the ``if`` block runs to the end of the script or
when indentation shows where the block ends (dedented lines close the block).
Blocks may be nested.

Conditions are evaluated *after* ``$variable`` replacement, so they operate
on plain strings. Supported operators (in order of matching priority)::

    ==  !=  >=  <=  >  <  contains  startswith  endswith  in

Multiple clauses may be combined with ``and`` / ``or`` and negated with
``not``. A bare value (no operator) is truthy unless it is empty or one of
``0``, ``false``, ``no``, ``none``, ``null``.
"""

import re

_COMPARISON_OPS = ("==", "!=", ">=", "<=", ">", "<")

_WORD_OPS = ("contains", "startswith", "endswith", "in")

_FALSY = {"", "0", "false", "no", "none", "null", "nil", "[]", "{}"}


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _as_number(value: str):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compare(left: str, op: str, right: str) -> bool:
    left = _strip_quotes(left.strip())
    right = _strip_quotes(right.strip())

    if op == "contains":
        return right.lower() in left.lower()
    if op == "startswith":
        return left.lower().startswith(right.lower())
    if op == "endswith":
        return left.lower().endswith(right.lower())
    if op == "in":
        return left.lower() in right.lower()

    left_num = _as_number(left)
    right_num = _as_number(right)
    if left_num is not None and right_num is not None:
        if op == "==":
            return left_num == right_num
        if op == "!=":
            return left_num != right_num
        if op == ">":
            return left_num > right_num
        if op == "<":
            return left_num < right_num
        if op == ">=":
            return left_num >= right_num
        if op == "<=":
            return left_num <= right_num

    if op == "==":
        return left.lower() == right.lower()
    if op == "!=":
        return left.lower() != right.lower()
    if op == ">":
        return left.lower() > right.lower()
    if op == "<":
        return left.lower() < right.lower()
    if op == ">=":
        return left.lower() >= right.lower()
    if op == "<=":
        return left.lower() <= right.lower()
    return False


def _split_top_level(text: str, keyword: str) -> list:
    """Split ``text`` on ``keyword`` surrounded by whitespace (case-insensitive)."""
    pattern = re.compile(rf"\s+{keyword}\s+", re.IGNORECASE)
    parts, start = [], 0
    for match in pattern.finditer(text):
        parts.append(text[start : match.start()])
        start = match.end()
    parts.append(text[start:])
    return parts


def _eval_atom(atom: str) -> bool:
    atom = atom.strip()
    if not atom:
        return False

    negated = False
    lowered = atom.lower()
    if lowered == "not":
        return False
    if lowered.startswith("not "):
        negated = True
        atom = atom[4:].strip()

    # Strip one layer of wrapping parentheses: ( ... )
    if len(atom) >= 2 and atom.startswith("(") and atom.endswith(")"):
        atom = atom[1:-1].strip()

    result = False
    matched = False

    for op in _COMPARISON_OPS:
        if op in atom:
            left, _, right = atom.partition(op)
            # Guard against `>=` being split as `>` + `=...`: partition on
            # the first occurrence is fine because ops are ordered longest-first
            # only when checking; instead re-derive: if op is >/</= variants,
            # ensure we matched the longest operator at this position.
            if op in (">", "<") and (left.endswith("=") or right.startswith("=")):
                continue
            result = _compare(left, op, right)
            matched = True
            break

    if not matched:
        for op in _WORD_OPS:
            pieces = re.split(rf"\s+{op}\s+", atom, maxsplit=1, flags=re.IGNORECASE)
            if len(pieces) == 2:
                result = _compare(pieces[0], op, pieces[1])
                matched = True
                break

    if not matched:
        result = _strip_quotes(atom).lower() not in _FALSY

    return not result if negated else result


def evaluate_condition_text(resolved: str) -> bool:
    """Evaluate an already variable-resolved condition string."""
    resolved = resolved.strip()
    if resolved.endswith(":"):
        resolved = resolved[:-1].strip()
    if not resolved:
        return False
    for or_part in _split_top_level(resolved, "or"):
        if all(_eval_atom(atom) for atom in _split_top_level(or_part, "and")):
            return True
    return False


async def evaluate_condition(ctx, engine, raw_expr: str) -> bool:
    """Replace ``$variables`` in ``raw_expr`` then evaluate it.

    Returns ``False`` (and never raises) on empty expressions so a bare
    ``if:`` line is a useful error instead of a crash; the engine logs it.
    """
    if raw_expr is None:
        return False
    resolved = await engine.replace_vars(ctx, raw_expr.strip())
    if not resolved.strip():
        return False
    return evaluate_condition_text(resolved)


def parse_if_header(stripped: str):
    """Parse an ``if`` / ``elif`` header line.

    Returns ``(keyword, expression)`` where keyword is ``"if"`` or ``"elif"``,
    or ``None`` when the line is not a conditional header.
    """
    core = stripped[:-1].strip() if stripped.endswith(":") else stripped
    core_low = core.lower()
    if core_low == "if" or core_low.startswith("if ") or core_low.startswith("if("):
        return ("if", core[2:].strip())
    if core_low == "elif" or core_low.startswith("elif ") or core_low.startswith("elif("):
        return ("elif", core[4:].strip())
    return None


def is_else(stripped: str) -> bool:
    low = stripped.lower().rstrip(":").strip()
    return low == "else"


def is_endif(stripped: str) -> bool:
    low = stripped.lower().rstrip(":").strip()
    return low in ("endif", "end if", "end")

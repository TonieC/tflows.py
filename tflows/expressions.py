"""Expression evaluation for tflows scripts.

Used by ``let``, ``return``, ``for``, and arithmetic on the right-hand side
of assignments. Template substitution (``$name``) still happens first so
existing variables keep working; leftover identifiers then resolve against
local variables.

Supported operators (highest precedence first)::

    unary + - not
    * / %
    + -
    == != > < >= <= contains startswith endswith in
    and
    or
"""

from __future__ import annotations

import ast
import operator
import re

from .runtime import FlowValue, as_list, is_truthy, stringify, to_number

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Gt: operator.gt,
    ast.Lt: operator.lt,
    ast.GtE: operator.ge,
    ast.LtE: operator.le,
}

_WORD_OPS = ("contains", "startswith", "endswith")


def _locals_of(ctx) -> dict:
    return getattr(ctx, "locals", None) or {}


def _get_local(ctx, name: str):
    store = _locals_of(ctx)
    if name in store:
        return store[name]
    # Case-insensitive fallback so $Name and Name match `let name = ...`.
    lowered = name.lower()
    for key, value in store.items():
        if key.lower() == lowered:
            return value
    return None


def lookup_local(ctx, name: str):
    """Return a local value, or ``None`` when the name is not defined."""
    if ctx is None:
        return None
    return _get_local(ctx, name)


def split_assignment(text: str):
    """Split ``name = expr`` outside quotes. Returns ``(name, expr)`` or ``None``."""
    quote = None
    i = 0
    while i < len(text):
        char = text[i]
        if quote is not None:
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        elif char == "=" and not (i > 0 and text[i - 1] in "=!<>"):
            nxt = text[i + 1] if i + 1 < len(text) else ""
            if nxt != "=":
                left = text[:i].strip()
                right = text[i + 1 :].strip()
                if _IDENT_RE.match(left):
                    return left, right
        i += 1
    return None


def parse_let(stripped: str):
    """Parse ``let name = expr`` or ``let name expr``. Returns ``(name, expr)``."""
    core = stripped.strip()
    if not core.lower().startswith("let "):
        return None
    rest = core[4:].strip()
    assigned = split_assignment(rest)
    if assigned is not None:
        return assigned
    parts = rest.split(None, 1)
    if not parts or not _IDENT_RE.match(parts[0]):
        return None
    return parts[0], parts[1] if len(parts) > 1 else ""


def parse_set_local(stripped: str):
    """Parse bare ``name = expr`` reassignment of an existing local."""
    assigned = split_assignment(stripped)
    if assigned is None:
        return None
    return assigned


def _coerce_pair(left, right):
    left_n = to_number(left)
    right_n = to_number(right)
    if left_n is not None and right_n is not None:
        return left_n, right_n
    return stringify(left), stringify(right)


def _apply_bin(op, left, right):
    if isinstance(op, ast.Add):
        left_n = to_number(left)
        right_n = to_number(right)
        if left_n is not None and right_n is not None:
            return left_n + right_n
        return stringify(left) + stringify(right)
    if isinstance(op, (ast.Sub, ast.Mult, ast.Div, ast.Mod)):
        left_n = to_number(left)
        right_n = to_number(right)
        if left_n is None or right_n is None:
            return 0 if isinstance(op, (ast.Sub, ast.Mult)) else (0 if isinstance(op, ast.Mod) else 0)
        if isinstance(op, ast.Div) and right_n == 0:
            return 0
        if isinstance(op, ast.Mod) and right_n == 0:
            return 0
        result = _BIN_OPS[type(op)](left_n, right_n)
        if isinstance(result, float) and result.is_integer():
            return int(result)
        return result
    left_c, right_c = _coerce_pair(left, right)
    if isinstance(left_c, str) and isinstance(right_c, str) and type(op) in (ast.Eq, ast.NotEq, ast.Gt, ast.Lt, ast.GtE, ast.LtE):
        if type(op) is ast.Eq:
            return left_c.lower() == right_c.lower()
        if type(op) is ast.NotEq:
            return left_c.lower() != right_c.lower()
        left_c, right_c = left_c.lower(), right_c.lower()
    fn = _BIN_OPS.get(type(op))
    if fn is None:
        return False
    return fn(left_c, right_c)


def _word_ops_to_python(expr: str) -> str:
    """Rewrite ``a contains b`` into a call the AST evaluator understands."""
    # Protect quoted strings first via a placeholder scan.
    out = []
    i = 0
    quote = None
    lower = expr
    while i < len(lower):
        char = lower[i]
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
        matched = False
        for word in _WORD_OPS:
            pattern = f" {word} "
            if lower[i : i + len(pattern)].lower() == pattern:
                out.append(f" __{word}__ ")
                i += len(pattern)
                matched = True
                break
        if not matched:
            out.append(char)
            i += 1
    return "".join(out)


def _eval_ast(node, ctx):
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body, ctx)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        local = lookup_local(ctx, node.id)
        if local is not None:
            return local.value if isinstance(local, FlowValue) else local
        # Unresolved identifiers become themselves (string) so `hello == hello`
        # and bare words in expressions keep working after $var replacement.
        return node.id
    if isinstance(node, ast.UnaryOp):
        value = _eval_ast(node.operand, ctx)
        if isinstance(node.op, ast.Not):
            return not is_truthy(value)
        if isinstance(node.op, ast.USub):
            number = to_number(value)
            return 0 if number is None else -number
        if isinstance(node.op, ast.UAdd):
            number = to_number(value)
            return 0 if number is None else number
        return value
    if isinstance(node, ast.BinOp):
        return _apply_bin(node.op, _eval_ast(node.left, ctx), _eval_ast(node.right, ctx))
    if isinstance(node, ast.Compare):
        left = _eval_ast(node.left, ctx)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_ast(comparator, ctx)
            if isinstance(op, ast.In):
                if not (stringify(left).lower() in stringify(right).lower()):
                    return False
            elif isinstance(op, ast.NotIn):
                if stringify(left).lower() in stringify(right).lower():
                    return False
            else:
                if not _apply_bin(op, left, right):
                    return False
            left = right
        return True
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            result = True
            for value in node.values:
                result = _eval_ast(value, ctx)
                if not is_truthy(result):
                    return result
            return result
        result = False
        for value in node.values:
            result = _eval_ast(value, ctx)
            if is_truthy(result):
                return result
        return result
    if isinstance(node, ast.List):
        return [_eval_ast(elt, ctx) for elt in node.elts]
    if isinstance(node, ast.Tuple):
        return [_eval_ast(elt, ctx) for elt in node.elts]
    if isinstance(node, ast.Dict):
        return {
            _eval_ast(k, ctx): _eval_ast(v, ctx)
            for k, v in zip(node.keys, node.values)
            if k is not None
        }
    if isinstance(node, ast.Subscript):
        target = _eval_ast(node.value, ctx)
        sl = node.slice
        key = _eval_ast(sl, ctx)
        if isinstance(target, dict):
            return target.get(key, target.get(str(key), ""))
        if isinstance(target, (list, tuple)):
            try:
                return target[int(key)]
            except (TypeError, ValueError, IndexError):
                return ""
        if isinstance(target, str):
            try:
                parsed = __import__("json").loads(target)
                return _eval_ast(
                    ast.Subscript(value=ast.Constant(parsed), slice=ast.Constant(key), ctx=ast.Load()),
                    ctx,
                ) if False else (
                    parsed.get(key, parsed.get(str(key), ""))
                    if isinstance(parsed, dict)
                    else ""
                )
            except Exception:
                return ""
        return ""
    if isinstance(node, ast.Attribute):
        target = _eval_ast(node.value, ctx)
        from .runtime import _get_field

        return _get_field(target, node.attr)
    if isinstance(node, ast.Call):
        # Only the rewritten word-ops (`__contains__` etc.) are allowed.
        if isinstance(node.func, ast.Name) and node.func.id.startswith("__") and node.func.id.endswith("__"):
            op = node.func.id.strip("_")
            if len(node.args) != 2:
                return False
            left = stringify(_eval_ast(node.args[0], ctx))
            right = stringify(_eval_ast(node.args[1], ctx))
            if op == "contains":
                return right.lower() in left.lower()
            if op == "startswith":
                return left.lower().startswith(right.lower())
            if op == "endswith":
                return left.lower().endswith(right.lower())
        return ""
    if isinstance(node, ast.JoinedStr):  # f-string — treat as concat of values
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            else:
                parts.append(stringify(_eval_ast(value, ctx)))
        return "".join(parts)
    return ""


def evaluate_expression(ctx, text: str):
    """Evaluate ``text`` (already $variable-resolved) to a Python value."""
    text = (text or "").strip()
    if not text:
        return ""
    # Word-operator rewrite: `a contains b` -> `__contains__(a, b)` is awkward
    # with infix, so we keep a tiny custom split instead of AST for those.
    rewritten = _rewrite_word_ops(text)
    try:
        tree = ast.parse(rewritten, mode="eval")
    except SyntaxError:
        # Fall back: identifier -> local, otherwise the raw text.
        local = lookup_local(ctx, text)
        if local is not None:
            return local.value if isinstance(local, FlowValue) else local
        return text.strip().strip("'\"")
    try:
        return _eval_ast(tree, ctx)
    except Exception:
        return text.strip().strip("'\"")


def _rewrite_word_ops(text: str) -> str:
    """Turn ``left contains right`` into ``__contains__(left, right)``."""
    result = text
    for word in _WORD_OPS:
        pattern = re.compile(rf"(.+?)\s+{word}\s+(.+)", re.IGNORECASE)
        match = pattern.fullmatch(result.strip())
        if match and not _inside_quotes(result, match.start(0) if False else 0):
            # Only rewrite when the operator is at the top level (not quoted).
            if _top_level_word(result, word):
                left, right = _split_word_op(result, word)
                result = f"__{word}__({left}, {right})"
    return result


def _inside_quotes(text: str, index: int) -> bool:
    quote = None
    for i, char in enumerate(text):
        if i >= index:
            break
        if quote is None and char in ("'", '"'):
            quote = char
        elif char == quote:
            quote = None
    return quote is not None


def _top_level_word(text: str, word: str) -> bool:
    pattern = re.compile(rf"\s+{word}\s+", re.IGNORECASE)
    quote = None
    i = 0
    while i < len(text):
        char = text[i]
        if quote is not None:
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        else:
            match = pattern.match(text, i)
            if match:
                return True
        i += 1
    return False


def _split_word_op(text: str, word: str):
    pattern = re.compile(rf"\s+{word}\s+", re.IGNORECASE)
    quote = None
    i = 0
    while i < len(text):
        char = text[i]
        if quote is not None:
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        else:
            match = pattern.match(text, i)
            if match:
                return text[:i].strip(), text[match.end() :].strip()
        i += 1
    return text, ""


_LONE_VAR_RE = re.compile(
    r"^\$(\w+)((?:\.[A-Za-z_]\w*|\[[^\[\]]*?\])*)(?:\(([^()]*)\))?$"
)


async def resolve_expression(ctx, engine, raw: str):
    """Replace ``$variables``, then evaluate arithmetic / locals.

    A lone ``$name`` / ``$name.path`` keeps the underlying Python value
    (list, dict, number, HttpResponse) so ``let data = json.parse ...``
    round-trips. Mixed text still stringifies via ``replace_vars``.
    """
    raw = "" if raw is None else str(raw)
    stripped = raw.strip()
    resolver = getattr(engine, "resolve_var_value", None)
    if stripped.startswith("$") and callable(resolver):
        match = _LONE_VAR_RE.fullmatch(stripped)
        if match:
            found, value = await resolver(
                ctx, match.group(1), match.group(3) or "", match.group(2) or ""
            )
            if found:
                return value
    resolved = await engine.replace_vars(ctx, raw)
    return evaluate_expression(ctx, resolved)


def expression_to_string(value) -> str:
    return stringify(value)


def iterate(value):
    return as_list(value)

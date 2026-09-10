"""Load and import ``.flow`` script files.

Security: imports are restricted to a project root (the directory of the
first loaded file, or ``engine.script_root``). Path traversal (``..``) and
absolute paths outside that root are rejected. Circular imports are
detected and reported; duplicate imports are skipped.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .runtime import ScriptFunction
from .syntax import (
    parse_command_header,
    parse_context_menu_header,
    parse_function_header,
    parse_import,
    parse_on_component,
    parse_on_where,
)
from .events import parse_on_header
from .scheduler import parse_cron_header, parse_every_header

logger = logging.getLogger("tflows.scripts")

_MAX_IMPORT_DEPTH = 16
_ALLOWED_SUFFIXES = (".flow", ".tflow")


class ImportError_(Exception):
    """Raised when a script import fails for a security or I/O reason."""


def _safe_resolve(root: Path, target: str) -> Path:
    if not target or target.strip() in (".", ""):
        raise ImportError_("empty import path")
    raw = target.strip().strip("'\"")
    # Reject obvious traversal / URI / absolute-outside-root attempts.
    if raw.startswith(("http://", "https://", "file://")):
        raise ImportError_(f"refusing remote import: {raw!r}")
    candidate = Path(raw)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ImportError_(f"import path escapes script root: {raw!r}") from exc
    if resolved.suffix.lower() in _ALLOWED_SUFFIXES:
        return resolved
    if resolved.suffix == "":
        with_flow = resolved.with_suffix(".flow")
        if with_flow.exists():
            return with_flow
        with_tflow = resolved.with_suffix(".tflow")
        if with_tflow.exists():
            return with_tflow
    raise ImportError_(f"refusing non-script import: {raw!r}")


def read_script(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ImportError_(f"cannot read {path}: {exc}") from exc


async def import_script(engine, ctx, target: str, *, origin: str | None = None):
    """Load ``target`` relative to the current script / engine root.

    Registers any ``function`` definitions onto the engine (and bot). The
    rest of the file is executed immediately so top-level ``let`` / ``set``
    / extra ``import`` lines run once.
    """
    root = _script_root(engine, ctx, origin)
    path = _safe_resolve(root, target)
    key = str(path)
    if key in engine._loading:
        raise ImportError_(f"circular import: {target}")
    if key in engine._loaded:
        return engine._loaded[key]
    if len(engine._loading) >= _MAX_IMPORT_DEPTH:
        raise ImportError_(f"import nesting exceeds {_MAX_IMPORT_DEPTH}")
    if not path.is_file():
        raise ImportError_(f"script not found: {target}")

    engine._loading.add(key)
    try:
        source = read_script(path)
        engine._loaded[key] = source
        doc = parse_document(source, filename=key)
        for name, fn in doc["functions"].items():
            engine.script_functions[name] = fn
            bot = getattr(ctx, "bot", None)
            if bot is not None:
                bot.script_functions[name] = fn
        bot = getattr(ctx, "bot", None)
        if bot is not None and hasattr(bot, "_apply_document"):
            # Register commands / events / menus on the bot, skip functions
            # we already copied so they are not duplicated.
            leftover = dict(doc)
            leftover["functions"] = {}
            bot._apply_document(leftover, key)
        previous = getattr(ctx, "filename", "")
        ctx.filename = key
        try:
            if doc["prelude"].strip():
                await engine.run(ctx, doc["prelude"])
        finally:
            ctx.filename = previous
        return source
    finally:
        engine._loading.discard(key)


def _script_root(engine, ctx, origin: str | None) -> Path:
    if engine.script_root:
        return Path(engine.script_root)
    filename = origin or getattr(ctx, "filename", "") or ""
    if filename:
        return Path(filename).resolve().parent
    bot = getattr(ctx, "bot", None)
    root = getattr(bot, "script_root", None) if bot is not None else None
    if root:
        return Path(root)
    return Path.cwd()


def extract_functions(source: str) -> dict[str, ScriptFunction]:
    """Parse ``function`` blocks out of ``source`` without executing it."""
    functions = {}
    lines = (source or "").split("\n")
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        header = parse_function_header(stripped)
        if header is None:
            i += 1
            continue
        name, params = header
        body = []
        i += 1
        while i < len(lines):
            s = lines[i].strip().lower().rstrip(":").strip()
            if s in ("endfunction", "end function", "endfn"):
                i += 1
                break
            # Dedent at column 0 that's not a comment ends the function when
            # no explicit ender is given — but keep indented / nested lines.
            raw = lines[i]
            indent = len(raw.expandtabs(4)) - len(raw.expandtabs(4).lstrip())
            if body and indent == 0 and raw.strip() and not raw.strip().startswith(("//", "#", "--")):
                if parse_function_header(raw.strip()) is not None:
                    break
                if parse_import(raw.strip()) is not None:
                    break
            body.append(raw)
            i += 1
        functions[name] = ScriptFunction(name=name, params=params, body="\n".join(body))
    return functions


def load_file(engine, path: str) -> str:
    """Synchronous helper used by ``tflows check`` and ``bot.load``."""
    p = Path(path)
    return p.read_text(encoding="utf-8")


def _indent(raw: str) -> int:
    return len(raw.expandtabs(4)) - len(raw.expandtabs(4).lstrip())


def _collect_indented(lines, start):
    """Collect body lines for a header at ``start``. Returns (body, next_index)."""
    header_indent = _indent(lines[start])
    body = []
    i = start + 1
    saw = False
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        indent = _indent(raw)
        if not stripped or stripped.startswith(("//", "#", "--")):
            body.append(raw)
            i += 1
            continue
        if saw and indent <= header_indent:
            break
        body.append(raw)
        saw = True
        i += 1
    return body, i


def parse_document(source: str, filename: str = ""):
    """Split a .flow file into functions, commands, events, and leftover body.

    Top-level ``function`` / ``command`` / ``on ...`` / ``every`` / ``cron``
    / ``context`` blocks are extracted. Remaining lines (imports, lets) are
    returned as ``prelude`` so they still run once on load.
    """
    lines = (source or "").split("\n")
    functions = {}
    commands = []
    events = []
    schedules = []
    context_menus = []
    prelude = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith(("//", "#", "--")):
            prelude.append(raw)
            i += 1
            continue

        fn_header = parse_function_header(stripped)
        if fn_header is not None:
            name, params = fn_header
            body, i = _collect_indented(lines, i)
            functions[name] = ScriptFunction(
                name=name, params=params, body="\n".join(body), filename=filename
            )
            continue

        cmd_header = parse_command_header(stripped)
        if cmd_header is not None:
            body, i = _collect_indented(lines, i)
            commands.append({"name": cmd_header, "code": "\n".join(body), "filename": filename})
            continue

        on_where = parse_on_where(stripped)
        if on_where is not None:
            event, where = on_where
            body, i = _collect_indented(lines, i)
            events.append({"event": event, "code": "\n".join(body), "where": where, "filename": filename})
            continue

        on_comp = parse_on_component(stripped)
        if on_comp is not None:
            kind, custom_id = on_comp
            body, i = _collect_indented(lines, i)
            events.append(
                {
                    "event": kind,
                    "code": "\n".join(body),
                    "where": None,
                    "custom_id": custom_id,
                    "filename": filename,
                }
            )
            continue

        on_header = parse_on_header(stripped)
        if on_header is not None:
            body, i = _collect_indented(lines, i)
            events.append({"event": on_header, "code": "\n".join(body), "where": None, "filename": filename})
            continue

        ctx_header = parse_context_menu_header(stripped)
        if ctx_header is not None:
            kind, name, attrs = ctx_header
            body, i = _collect_indented(lines, i)
            context_menus.append(
                {"kind": kind, "name": name or attrs.get("name", kind), "code": "\n".join(body), "filename": filename}
            )
            continue

        if parse_every_header(stripped) is not None or parse_cron_header(stripped) is not None:
            body, i = _collect_indented(lines, i)
            schedules.append({"header": stripped, "code": "\n".join(body), "filename": filename})
            continue

        prelude.append(raw)
        i += 1

    return {
        "functions": functions,
        "commands": commands,
        "events": events,
        "schedules": schedules,
        "context_menus": context_menus,
        "prelude": "\n".join(prelude),
        "filename": filename,
    }

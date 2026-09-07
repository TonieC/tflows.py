"""Static checks for tflows scripts (``tflows check``).

Reports syntax problems without executing Discord side effects. Unknown
functions / variables are warnings because scripts may register extras at
runtime.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .conditionals import is_else, is_endif, parse_if_header
from .events import EVENT_MAP, parse_on_header
from .expressions import parse_let
from .syntax import (
    is_break,
    is_continue,
    is_endbutton,
    is_endfunction,
    is_endfor,
    is_endmodal,
    is_endrepeat,
    is_endselect,
    parse_button_header,
    parse_call,
    parse_for_header,
    parse_function_header,
    parse_import,
    parse_modal_header,
    parse_on_component,
    parse_on_where,
    parse_repeat_header,
    parse_return,
    parse_select_header,
)


@dataclass
class Diagnostic:
    filename: str
    line: int
    column: int
    severity: str
    message: str

    def format(self) -> str:
        loc = f"{self.filename}:{self.line}:{self.column}"
        return f"{loc}\n{self.severity.capitalize()}: {self.message}"

    def __str__(self) -> str:
        return self.format()


_CORE_FUNCTIONS = {
    "send",
    "reply",
    "log",
    "wait",
    "react",
    "delete",
    "clear",
    "ping",
    "set",
    "get",
    "del",
    "incr",
    "embed",
    "role",
    "kick",
    "ban",
    "unban",
    "timeout",
    "channel",
    "thread",
    "http.get",
    "http.post",
    "http.put",
    "http.patch",
    "http.delete",
    "json.parse",
    "json.dump",
    "json.stringify",
    "defer",
    "ephemeral",
    "show_modal",
    "server",
    "membercount",
}

_CORE_VARS = {
    "user",
    "author",
    "server",
    "guild",
    "channel",
    "bot",
    "args",
    "arg",
    "argcount",
    "get",
    "state",
    "hasrole",
    "hasperm",
    "isowner",
    "ping",
    "time",
    "uptime",
    "membercount",
    "random",
    "id",
    "avatar",
    "image",
    "prefix",
    "command",
    "message",
    "emoji",
    "value",
    "interaction",
    "members",
    "roles",
    "channels",
    "target",
    "content",
    "input",
    "response",
}


def _indent(raw: str) -> int:
    return len(raw.expandtabs(4)) - len(raw.expandtabs(4).lstrip())


def check_source(source: str, filename: str = "<script>", registry=None) -> list[Diagnostic]:
    """Return diagnostics for a script source string."""
    diagnostics: list[Diagnostic] = []
    lines = (source or "").split("\n")
    stack: list[tuple[str, int, int]] = []  # (kind, line, indent)
    defined_functions: set[str] = set()
    defined_locals: set[str] = set()
    known_functions = set(_CORE_FUNCTIONS)
    known_vars = set(_CORE_VARS)
    if registry is not None:
        known_functions.update(registry.function_names())
        known_vars.update(registry.var_names())

    def error(line_no: int, column: int, message: str, severity="error"):
        diagnostics.append(
            Diagnostic(filename=filename, line=line_no, column=max(1, column), severity=severity, message=message)
        )

    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        line_no = i + 1
        column = _indent(raw) + 1
        if not stripped or stripped.startswith(("//", "#", "--")):
            i += 1
            continue

        if_header = parse_if_header(stripped)
        if if_header is not None and if_header[0] == "if":
            if not if_header[1]:
                error(line_no, column, "empty condition")
            stack.append(("if", line_no, _indent(raw)))
            i += 1
            continue
        if is_endif(stripped):
            if not stack or stack[-1][0] != "if":
                error(line_no, column, "endif without matching if")
            else:
                stack.pop()
            i += 1
            continue
        if is_else(stripped) or (if_header is not None and if_header[0] == "elif"):
            if not stack or stack[-1][0] != "if":
                error(line_no, column, f"{stripped.split()[0]} without matching if")
            i += 1
            continue

        for_header = parse_for_header(stripped)
        if for_header is not None:
            if not for_header[1]:
                error(line_no, column, "for-loop missing iterable")
            stack.append(("for", line_no, _indent(raw)))
            defined_locals.add(for_header[0])
            i += 1
            continue
        if stripped.lower().rstrip(":").strip() in ("endfor", "end for"):
            if not stack or stack[-1][0] != "for":
                error(line_no, column, "endfor without matching for")
            else:
                stack.pop()
            i += 1
            continue

        repeat_header = parse_repeat_header(stripped)
        if repeat_header is not None:
            stack.append(("repeat", line_no, _indent(raw)))
            i += 1
            continue
        if stripped.lower().rstrip(":").strip() in ("endrepeat", "end repeat"):
            if not stack or stack[-1][0] != "repeat":
                error(line_no, column, "endrepeat without matching repeat")
            else:
                stack.pop()
            i += 1
            continue

        fn_header = parse_function_header(stripped)
        if fn_header is not None:
            defined_functions.add(fn_header[0])
            known_functions.add(fn_header[0])
            stack.append(("function", line_no, _indent(raw)))
            for param in fn_header[1]:
                defined_locals.add(param)
            i += 1
            continue
        if is_endfunction(stripped):
            if not stack or stack[-1][0] != "function":
                error(line_no, column, "endfunction without matching function")
            else:
                stack.pop()
            i += 1
            continue

        if parse_button_header(stripped) is not None and stripped.lower().startswith("button"):
            stack.append(("button", line_no, _indent(raw)))
            i += 1
            continue
        if is_endbutton(stripped):
            if stack and stack[-1][0] == "button":
                stack.pop()
            i += 1
            continue
        if parse_select_header(stripped) is not None and stripped.lower().startswith("select"):
            stack.append(("select", line_no, _indent(raw)))
            i += 1
            continue
        if is_endselect(stripped):
            if stack and stack[-1][0] == "select":
                stack.pop()
            i += 1
            continue
        if parse_modal_header(stripped) is not None and stripped.lower().startswith("modal"):
            stack.append(("modal", line_no, _indent(raw)))
            i += 1
            continue
        if is_endmodal(stripped):
            if stack and stack[-1][0] == "modal":
                stack.pop()
            i += 1
            continue

        if stripped == "embed":
            stack.append(("embed", line_no, _indent(raw)))
            i += 1
            continue
        if stripped == "endembed":
            if not stack or stack[-1][0] != "embed":
                error(line_no, column, "endembed without matching embed")
            else:
                stack.pop()
            i += 1
            continue

        imported = parse_import(stripped)
        if imported is not None:
            if ".." in imported.replace("\\", "/").split("/"):
                error(line_no, column, f"import path must not contain '..': {imported}")
            i += 1
            continue

        on_where = parse_on_where(stripped)
        if on_where is not None:
            event, _cond = on_where
            if event not in EVENT_MAP and event not in ("button", "select", "modal"):
                error(line_no, column, f"unknown event {event!r}", severity="warning")
            i += 1
            continue
        on_comp = parse_on_component(stripped)
        if on_comp is not None:
            i += 1
            continue
        on_header = parse_on_header(stripped)
        if on_header is not None:
            if on_header not in EVENT_MAP:
                error(line_no, column, f"unknown event {on_header!r}", severity="warning")
            i += 1
            continue

        if is_break(stripped) or is_continue(stripped):
            kinds = {k for k, _, _ in stack}
            if "for" not in kinds and "repeat" not in kinds:
                error(line_no, column, f"{stripped} outside of a loop")
            i += 1
            continue
        if parse_return(stripped) is not None:
            i += 1
            continue

        let = parse_let(stripped)
        if let is not None:
            defined_locals.add(let[0])
            i += 1
            continue

        # Unknown function (first token).
        call = parse_call(stripped)
        name = call[0] if call is not None else stripped.split()[0]
        skip = {
            "if",
            "elif",
            "else",
            "endif",
            "for",
            "repeat",
            "function",
            "let",
            "return",
            "break",
            "continue",
            "import",
            "on",
            "every",
            "cron",
            "cooldown",
            "require",
            "option",
            "input",
            "command",
            "context",
        }
        if name.lower() not in skip and name not in known_functions and name not in defined_functions:
            if name.isidentifier() or "." in name:
                error(line_no, column, f"unknown function `{name}`", severity="warning")
        i += 1

    for kind, line_no, _indent_at in stack:
        expected = {
            "if": "endif",
            "for": "endfor",
            "repeat": "endrepeat",
            "function": "endfunction",
            "embed": "endembed",
            "button": "endbutton",
            "select": "endselect",
            "modal": "endmodal",
        }.get(kind, "end " + kind)
        error(line_no, 1, f"unclosed {kind} block (expected `{expected}`)")

    return diagnostics


def check_file(path: str, registry=None) -> list[Diagnostic]:
    try:
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
    except OSError as exc:
        return [
            Diagnostic(filename=path, line=1, column=1, severity="error", message=f"cannot read file: {exc}")
        ]
    return check_source(source, filename=os.path.basename(path) or path, registry=registry)


def format_diagnostics(diagnostics: list[Diagnostic]) -> str:
    if not diagnostics:
        return "No issues found."
    return "\n\n".join(d.format() for d in diagnostics)

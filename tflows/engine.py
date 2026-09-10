"""The tflows script interpreter.

The :class:`Engine` executes text scripts line by line. Each line is either a
call to a registered function (``send hello world``), a ``$variable`` template
that gets resolved inline, an ``embed``/``endembed`` block, a conditional
(``if``/``elif``/``else``/``endif``), a loop, a script-defined function, a
local assignment, or a declarative guard (``cooldown``/``require``).
"""

import asyncio
import logging
import re

import discord

from .conditionals import evaluate_condition, is_else, is_endif, parse_if_header
from .context import FlowContext
from .events import parse_on_header
from .expressions import (
    evaluate_expression,
    lookup_local,
    parse_let,
    parse_set_local,
    resolve_expression,
)
from .guards import check_permission, parse_cooldown, parse_require
from .runtime import (
    FlowBreak,
    FlowContinue,
    FlowReturn,
    FlowValue,
    ScriptFunction,
    access_path,
    as_list,
    stringify,
    to_number,
)
from .scheduler import parse_cron_header, parse_every_header
from .syntax import (
    is_break,
    is_continue,
    is_defer,
    is_endbutton,
    is_endfunction,
    is_endfor,
    is_endmodal,
    is_endrepeat,
    is_endselect,
    is_ephemeral,
    parse_button_header,
    parse_call,
    parse_for_header,
    parse_function_header,
    parse_import,
    parse_input_line,
    parse_modal_header,
    parse_on_component,
    parse_on_where,
    parse_option_line,
    parse_repeat_header,
    parse_return,
    parse_select_header,
    split_call_args,
)
from .utils import parse_color

logger = logging.getLogger("tflows.engine")

# Matches $name, $name(arg), $name.field, $name[key], and combinations.
# Parenthesized arguments stay flat (no nesting) so replacement is predictable.
_VAR_PATTERN = re.compile(
    r"\$(\w+)((?:\.[A-Za-z_]\w*|\[[^\[\]]*?\])*)(?:\(([^()]*)\))?"
)

_EMBED_KEYS = ("title", "desc", "footer", "color", "thumbnail", "image", "timestamp", "author")

_COMMENT_PREFIXES = ("//", "#", "--")

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Engine:
    """Executes tflows scripts against a registry of functions and variables.

    Parameters
    ----------
    registry:
        The :class:`~tflows.registry.FunctionRegistry` to resolve against.
    """

    def __init__(self, registry):
        self.registry = registry
        self.script_functions: dict[str, ScriptFunction] = {}
        self.globals: dict[str, FlowValue] = {}
        self._loading: set[str] = set()
        self._loaded: dict[str, str] = {}
        self.script_root = None
        self._fn_depth = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_comment(line):
        return line.startswith(_COMMENT_PREFIXES)

    @staticmethod
    def _indent(raw_line):
        return len(raw_line.expandtabs(4)) - len(raw_line.expandtabs(4).lstrip())

    def _log_errors(self, ctx):
        bot = getattr(ctx, "bot", None)
        return getattr(bot, "log_errors", True) if bot is not None else True

    @staticmethod
    def _is_schedule_header(stripped):
        # Tolerated so scheduled scripts run verbatim when executed manually.
        return parse_every_header(stripped) is not None or parse_cron_header(stripped) is not None

    @staticmethod
    def _is_event_header(stripped):
        # Tolerated so event scripts run verbatim when executed manually.
        if parse_on_component(stripped) is not None:
            return True
        if parse_on_where(stripped) is not None:
            return True
        return parse_on_header(stripped) is not None

    def _script_functions(self, ctx) -> dict:
        combined = dict(self.script_functions)
        bot = getattr(ctx, "bot", None)
        extra = getattr(bot, "script_functions", None) if bot is not None else None
        if extra:
            combined.update(extra)
        return combined

    # ------------------------------------------------------------------
    # Variable resolution
    # ------------------------------------------------------------------
    async def resolve_var_value(self, ctx, name, args="", path=""):
        """Resolve ``$name`` to ``(found, value)`` without stringifying.

        ``found`` is False when the name is unknown so callers can leave the
        original text untouched. Script-defined functions are invoked when
        there is no local / extra / registered variable of the same name,
        which makes ``send $greet(Ada)`` interpolate the return value.
        """
        value = None
        found = False

        if ctx is not None and hasattr(ctx, "get_local"):
            local = ctx.get_local(name)
            if local is not None:
                value = local.value if isinstance(local, FlowValue) else local
                found = True

        if not found and ctx is not None:
            extras = getattr(ctx, "extras", None) or {}
            if name in extras:
                value = extras[name]
                found = True
            else:
                lowered = name.lower()
                for key, item in extras.items():
                    if str(key).lower() == lowered:
                        value = item
                        found = True
                        break

        if not found:
            global_value = self.globals.get(name)
            if global_value is not None:
                value = global_value.value if isinstance(global_value, FlowValue) else global_value
                found = True

        if found:
            if path:
                value = access_path(value, path)
            if args:
                from .runtime import _get_field

                field = _get_field(value, args)
                if field != "" and field is not None:
                    value = field
                else:
                    optioned = access_path(value, args if args[:1] in ".[" else "." + args)
                    if optioned not in ("", None) and optioned is not value:
                        value = optioned
                    else:
                        value = ""
            return True, value

        script_fn = self._script_functions(ctx).get(name)
        if script_fn is not None:
            arg_values = []
            if (args or "").strip():
                for item in split_call_args(args):
                    arg_values.append(await resolve_expression(ctx, self, item))
            value = await self._invoke_script_function(ctx, script_fn, arg_values)
            if path:
                value = access_path(value, path)
            return True, value

        handler = self.registry.get_var(name)
        if handler is None:
            return False, None

        result = handler(ctx, args)
        if asyncio.iscoroutine(result):
            result = await result
        if result is None:
            result = ""
        if path:
            result = access_path(result, path)
        return True, result

    async def resolve_var(self, ctx, name, args="", path=""):
        """Resolve a single ``$name(args)`` variable to a string.

        Returns ``None`` when the variable is not registered, so callers can
        leave the original text untouched.
        """
        found, value = await self.resolve_var_value(ctx, name, args, path)
        if not found:
            return None
        return stringify(value)

    async def replace_vars(self, ctx, text):
        """Replace every ``$variable`` / ``$variable(args)`` occurrence in text.

        Unknown variables are left as-is so typos do not silently corrupt
        output. Replacement happens from the last match to the first so that a
        resolved value is never re-scanned for new variables.
        """
        if text is None:
            return ""

        matches = list(_VAR_PATTERN.finditer(text))
        for match in reversed(matches):
            name = match.group(1)
            path = match.group(2) or ""
            args = match.group(3) or ""
            replacement = await self.resolve_var(ctx, name, args, path)
            if replacement is None:
                continue
            start, end = match.span()
            text = text[:start] + replacement + text[end:]

        return text

    # ------------------------------------------------------------------
    # Embed blocks
    # ------------------------------------------------------------------
    def _grab(self, block, key):
        match = re.search(rf"\${key}\[(.*?)\]", block, re.DOTALL)
        return match.group(1).strip() if match else None

    def _apply_embed(self, embed, key, value):
        """Apply a resolved embed directive to a discord.Embed instance."""
        key = key.lower()

        if key in ("title", "author"):
            if value:
                if key == "title":
                    embed.title = value
                else:
                    embed.set_author(name=value)
            return

        if key == "desc":
            embed.description = value or embed.description
            return

        if key == "footer":
            if value:
                embed.set_footer(text=value)
            return

        if key == "color":
            color = parse_color(value)
            if color is not None:
                embed.color = discord.Color(color)
            return

        if key == "thumbnail":
            if value:
                embed.set_thumbnail(url=value)
            return

        if key == "image":
            if value:
                embed.set_image(url=value)
            return

    async def parse_embed(self, ctx, block):
        """Parse and send an ``embed``/``endembed`` block."""
        block = block.replace("\r\n", "\n").strip()
        embed = discord.Embed()

        values = {}
        for key in _EMBED_KEYS:
            values[key] = self._grab(block, key)

        clean = re.sub(
            r"\$(title|desc|footer|color|thumbnail|image|timestamp|author)\[.*?\]",
            "",
            block,
            flags=re.DOTALL,
        ).strip()

        for key, raw in values.items():
            if not raw:
                continue
            resolved = await self.replace_vars(ctx, raw)
            if key == "timestamp":
                embed.timestamp = ctx.message.created_at
            else:
                self._apply_embed(embed, key, resolved)

        # Fall back to whatever text is left when no explicit $desc[...] given.
        if not values.get("desc") and clean:
            embed.description = await self.replace_vars(ctx, clean)

        kwargs = {}
        view = self._consume_view(ctx)
        if view is not None:
            kwargs["view"] = view
        await ctx.channel.send(embed=embed, **kwargs)

    def _consume_view(self, ctx):
        from .components import build_view

        return build_view(ctx)

    # ------------------------------------------------------------------
    # Guards (cooldown / require directives)
    # ------------------------------------------------------------------
    async def _handle_cooldown(self, ctx, stripped, state) -> bool | None:
        """Enforce a ``cooldown`` line. Returns False to abort, True to continue,
        None when the line is not a cooldown directive."""
        low = stripped.lower()
        if low != "cooldown" and not low.startswith("cooldown "):
            return None
        parsed = parse_cooldown(stripped)
        if parsed is None:
            logger.warning("[tflow] Invalid cooldown syntax: %s", stripped)
            await self._notify(ctx, f"Invalid cooldown syntax: `{stripped}` (expected e.g. `cooldown 5s per user`)")
            return False
        if state["cooldown_seen"]:
            return True  # first cooldown line wins
        state["cooldown_seen"] = True
        seconds, scope = parsed
        manager = self._cooldown_manager(ctx)
        if manager is None:
            return True
        from .guards import _scope_key

        command = getattr(ctx, "command_name", None) or "global"
        remaining = manager.check(command, scope, _scope_key(ctx, scope), seconds)
        if remaining > 0:
            await self._notify(
                ctx, f"Please wait {remaining:.0f}s before using `{command}` again."
            )
            return False
        return True

    async def _handle_require(self, ctx, stripped) -> bool | None:
        """Enforce a ``require`` line. Returns False to abort, True to continue,
        None when the line is not a require directive."""
        low = stripped.lower()
        if low != "require" and not low.startswith("require "):
            return None
        parsed = parse_require(stripped)
        if parsed is None:
            logger.warning("[tflow] Invalid require syntax: %s", stripped)
            await self._notify(
                ctx,
                f"Invalid require syntax: `{stripped}` "
                "(expected e.g. `require manage_messages`, `require role Mod`, `require owner`)",
            )
            return False  # fail closed on unparseable requirements
        kind, value = parsed
        if not check_permission(ctx, kind, value):
            await self._notify(ctx, "You do not have permission to use this command.")
            return False
        return True

    @staticmethod
    def _cooldown_manager(ctx):
        bot = getattr(ctx, "bot", None)
        manager = getattr(bot, "cooldowns", None) if bot is not None else None
        if manager is not None:
            return manager
        # Standalone engine use: keep an ephemeral manager on the context.
        if bot is None:
            return None
        from .guards import CooldownManager

        bot.cooldowns = CooldownManager()
        return bot.cooldowns

    async def _enforce_leading_guards(self, ctx, lines) -> bool:
        """Apply top-level ``cooldown`` / ``require`` before any other line."""
        guard_state = {"cooldown_seen": False}
        for raw in lines:
            if self._indent(raw) != 0:
                continue
            stripped = raw.strip()
            if not stripped or self._is_comment(stripped):
                continue
            cooldown = await self._handle_cooldown(ctx, stripped, guard_state)
            if cooldown is False:
                return False
            if cooldown is True:
                continue
            required = await self._handle_require(ctx, stripped)
            if required is False:
                return False
        return True

    async def _notify(self, ctx, text: str) -> None:
        try:
            await ctx.channel.send(text)
        except Exception:
            logger.exception("[tflow] Failed to send notice")

    # ------------------------------------------------------------------
    # Block collection (loops, functions, components)
    # ------------------------------------------------------------------
    def _collect_block(self, lines, start, header_indent, enders):
        """Collect an indented body starting after ``start``.

        Returns ``(body_lines, index_after_block)``.
        """
        body = []
        i = start + 1
        saw_body = False
        while i < len(lines):
            raw = lines[i]
            stripped = raw.strip()
            indent = self._indent(raw)
            if not stripped or self._is_comment(stripped):
                body.append(raw)
                i += 1
                continue
            if stripped.lower().rstrip(":").strip() in enders:
                i += 1
                break
            if saw_body and indent <= header_indent:
                break
            body.append(raw)
            saw_body = True
            i += 1
        return body, i

    def _register_function(self, ctx, fn: ScriptFunction):
        self.script_functions[fn.name] = fn
        bot = getattr(ctx, "bot", None)
        if bot is not None:
            bot.script_functions[fn.name] = fn

    # ------------------------------------------------------------------
    # Main interpreter loop
    # ------------------------------------------------------------------
    async def run(self, ctx, code):
        """Execute a script.

        ``ctx`` may be a raw :class:`discord.Message`, in which case it is
        wrapped in a :class:`FlowContext`, or a :class:`FlowContext` directly.

        Supports ``if``/``elif``/``else``/``endif`` conditionals (nestable),
        ``for``/``repeat`` loops, ``function`` definitions, ``let`` locals,
        ``cooldown``/``require`` guard directives, and tolerates leading
        ``every``/``cron``/``on`` headers from scheduled/event scripts.
        """
        if not isinstance(ctx, FlowContext):
            ctx = FlowContext.from_message(ctx)

        lines = (code or "").split("\n")
        if not await self._enforce_leading_guards(ctx, lines):
            return ctx.return_value

        try:
            await self._run_lines(ctx, lines, skip_leading_guards=True)
        except FlowReturn as ret:
            ctx.return_value = ret.value
            return ret.value
        except FlowBreak:
            logger.warning("[tflow] 'break' outside of a loop")
        except FlowContinue:
            logger.warning("[tflow] 'continue' outside of a loop")
        return ctx.return_value

    async def _run_lines(self, ctx, lines, *, loop_depth=0, skip_leading_guards=False):
        log_errors = self._log_errors(ctx)
        stack: list[dict] = []  # if-frames
        guard_state = {"cooldown_seen": False}
        i = 0

        def active() -> bool:
            return all(frame["branch_active"] for frame in stack)

        def close_dedented(indent: int, stripped: str) -> None:
            # `else`/`elif`/`endif` at any indent belong to their block.
            header = parse_if_header(stripped)
            if is_else(stripped) or is_endif(stripped) or (header is not None and header[0] == "elif"):
                return
            while stack and indent <= stack[-1]["if_indent"] and stack[-1]["saw_body"]:
                stack.pop()

        while i < len(lines):
            raw = lines[i]
            stripped = raw.strip()
            indent = self._indent(raw)

            if not stripped or self._is_comment(stripped):
                i += 1
                continue

            if skip_leading_guards and indent == 0:
                low = stripped.lower()
                if (
                    low == "cooldown"
                    or low.startswith("cooldown ")
                    or low == "require"
                    or low.startswith("require ")
                ):
                    i += 1
                    continue

            # ----- conditional headers -----
            if_header = parse_if_header(stripped)
            if if_header is not None and if_header[0] == "if":
                close_dedented(indent, stripped)
                # A nested `if` is itself an indented body line for outer frames.
                for frame in stack:
                    if indent > frame["if_indent"]:
                        frame["saw_body"] = True
                parent_active = active()
                _keyword, expr = if_header
                if not expr:
                    logger.warning("[tflow] Empty condition in line: %s", stripped)
                    result = False
                elif parent_active:
                    try:
                        result = await evaluate_condition(ctx, self, expr)
                    except Exception:
                        if log_errors:
                            logger.exception("[tflow] Failed to evaluate condition: %s", expr)
                        result = False
                else:
                    result = False
                stack.append(
                    {
                        "if_indent": indent,
                        "parent_active": parent_active,
                        "matched": bool(result) and parent_active,
                        "branch_active": bool(result) and parent_active,
                        "else_seen": False,
                        "saw_body": False,
                    }
                )
                i += 1
                continue

            if is_endif(stripped):
                if stack:
                    # Explicit terminator: always closes the innermost block.
                    stack.pop()
                    i += 1
                    continue
                # Outside any if-block: fall through to the unknown-function
                # path, preserving historical behavior for stray lines.
                try:
                    await self.execute_line(ctx, stripped)
                except FlowReturn:
                    raise
                except (FlowBreak, FlowContinue):
                    raise
                except Exception:
                    if log_errors:
                        logger.exception("[tflow] Error in line: %s", stripped)
                i += 1
                continue

            if is_else(stripped) or (if_header is not None and if_header[0] == "elif"):
                if not stack:
                    logger.warning("[tflow] '%s' without matching 'if'", stripped)
                    i += 1
                    continue
                frame = stack[-1]
                if frame["else_seen"]:
                    logger.warning("[tflow] Multiple 'else' branches for one 'if'")
                    frame["branch_active"] = False
                    i += 1
                    continue
                if is_else(stripped):
                    frame["else_seen"] = True
                    frame["branch_active"] = frame["parent_active"] and not frame["matched"]
                    if frame["branch_active"]:
                        frame["matched"] = True
                else:
                    _kw, expr = parse_if_header(stripped)
                    if frame["parent_active"] and not frame["matched"]:
                        try:
                            result = await evaluate_condition(ctx, self, expr)
                        except Exception:
                            if log_errors:
                                logger.exception("[tflow] Failed to evaluate condition: %s", expr)
                            result = False
                        frame["branch_active"] = bool(result)
                        if result:
                            frame["matched"] = True
                    else:
                        frame["branch_active"] = False
                i += 1
                continue

            # Dedent closes blocks whose body was indented.
            close_dedented(indent, stripped)
            is_active = active()
            if stack and indent > stack[-1]["if_indent"] and stripped:
                stack[-1]["saw_body"] = True

            # ----- embed block -----
            if stripped == "embed":
                i += 1
                block = []
                while i < len(lines):
                    if lines[i].strip() == "endembed":
                        break
                    block.append(lines[i])
                    i += 1
                if is_active:
                    try:
                        await self.parse_embed(ctx, "\n".join(block))
                    except Exception:
                        if log_errors:
                            logger.exception("[tflow] Failed to render embed block")
                i += 1
                continue

            # ----- schedule / event headers tolerated as no-ops -----
            if self._is_schedule_header(stripped) or self._is_event_header(stripped):
                i += 1
                continue

            # ----- function definition -----
            fn_header = parse_function_header(stripped)
            if fn_header is not None:
                name, params = fn_header
                body, i = self._collect_block(
                    lines, i, indent, {"endfunction", "end function", "endfn"}
                )
                if is_active:
                    fn = ScriptFunction(
                        name=name,
                        params=params,
                        body="\n".join(body),
                        filename=getattr(ctx, "filename", "") or "",
                    )
                    self._register_function(ctx, fn)
                continue

            # ----- loops -----
            for_header = parse_for_header(stripped)
            if for_header is not None:
                var_name, iterable_expr = for_header
                body, i = self._collect_block(
                    lines, i, indent, {"endfor", "end for"}
                )
                if is_active:
                    try:
                        await self._run_for(ctx, var_name, iterable_expr, body, log_errors)
                    except FlowReturn:
                        raise
                    except Exception:
                        if log_errors:
                            logger.exception("[tflow] Error in for-loop")
                continue

            repeat_header = parse_repeat_header(stripped)
            if repeat_header is not None:
                count_expr = repeat_header
                body, i = self._collect_block(
                    lines, i, indent, {"endrepeat", "end repeat"}
                )
                if is_active:
                    try:
                        await self._run_repeat(ctx, count_expr, body, log_errors)
                    except FlowReturn:
                        raise
                    except Exception:
                        if log_errors:
                            logger.exception("[tflow] Error in repeat-loop")
                continue

            # ----- component blocks -----
            button_header = parse_button_header(stripped)
            if button_header is not None and stripped.lower().startswith("button"):
                # Distinguish from a hypothetical `button` function call without attrs:
                # `button "Click" id=...` or `button "Click":` is a block.
                label, attrs = button_header
                body, i = self._collect_block(
                    lines, i, indent, {"endbutton", "end button"}
                )
                if is_active:
                    await self._handle_button(ctx, label, attrs, body)
                continue

            select_header = parse_select_header(stripped)
            if select_header is not None and (
                stripped.lower() == "select"
                or stripped.lower().startswith("select ")
                or stripped.lower().startswith("select:")
            ):
                attrs = select_header
                body, i = self._collect_block(
                    lines, i, indent, {"endselect", "end select"}
                )
                if is_active:
                    await self._handle_select(ctx, attrs, body)
                continue

            modal_header = parse_modal_header(stripped)
            if modal_header is not None and stripped.lower().startswith("modal"):
                title, attrs = modal_header
                body, i = self._collect_block(
                    lines, i, indent, {"endmodal", "end modal"}
                )
                if is_active:
                    await self._handle_modal(ctx, title, attrs, body)
                continue

            # ----- inactive lines: skip side effects -----
            if not is_active:
                i += 1
                continue

            # ----- control flow -----
            if is_break(stripped):
                raise FlowBreak()
            if is_continue(stripped):
                raise FlowContinue()
            ret = parse_return(stripped)
            if ret is not None:
                value = await resolve_expression(ctx, self, ret) if ret else ""
                raise FlowReturn(value)

            if is_defer(stripped):
                await self._handle_defer(ctx, stripped)
                i += 1
                continue
            if is_ephemeral(stripped):
                ctx.ephemeral = True
                i += 1
                continue

            # ----- import -----
            imported = parse_import(stripped)
            if imported is not None:
                try:
                    await self._handle_import(ctx, imported)
                except Exception as exc:
                    from .scripts import ImportError_ as _ImportError

                    if isinstance(exc, _ImportError):
                        raise
                    if log_errors:
                        logger.exception("[tflow] Failed to import %s", imported)
                i += 1
                continue

            # ----- let / reassignment -----
            let = parse_let(stripped)
            if let is not None:
                try:
                    await self._assign(ctx, let[0], let[1])
                except FlowReturn:
                    raise
                except Exception:
                    if log_errors:
                        logger.exception("[tflow] Error in let: %s", stripped)
                i += 1
                continue

            assigned = parse_set_local(stripped)
            if assigned is not None and (
                ctx.get_local(assigned[0]) is not None or assigned[0] in self.globals
            ):
                try:
                    await self._assign(ctx, assigned[0], assigned[1])
                except Exception:
                    if log_errors:
                        logger.exception("[tflow] Error in assignment: %s", stripped)
                i += 1
                continue

            # ----- guard directives -----
            cooldown = await self._handle_cooldown(ctx, stripped, guard_state)
            if cooldown is False:
                return
            if cooldown is True:
                i += 1
                continue
            required = await self._handle_require(ctx, stripped)
            if required is False:
                return
            if required is True:
                i += 1
                continue

            # ----- normal instruction -----
            try:
                await self.execute_line(ctx, stripped)
            except (FlowReturn, FlowBreak, FlowContinue):
                raise
            except Exception:
                if log_errors:
                    logger.exception("[tflow] Error in line: %s", stripped)

            i += 1

    async def _assign(self, ctx, name, expr):
        value = await self._eval_rhs(ctx, expr)
        ctx.set_local(name, value)

    async def _eval_rhs(self, ctx, expr: str):
        expr = (expr or "").strip()
        if not expr:
            return ""
        # `greet("Ada")` / `http.get(...)` with parentheses: evaluate args.
        call = parse_call(expr)
        if call is not None:
            result = await self._call_value(ctx, call[0], call[1])
            if result is not None:
                return result
        # `http.get "url"` / `json.parse {...}` without parens. The remainder
        # is a string after $var replacement, not a Python expression, so
        # `json.parse not-json` stays text instead of evaluating `not -json`.
        parts = expr.split(None, 1)
        if parts:
            fn_name = parts[0]
            rest = parts[1] if len(parts) > 1 else ""
            is_registry = self.registry.get(fn_name) is not None
            is_script = fn_name in self._script_functions(ctx)
            if is_registry or (is_script and rest):
                resolved = await self.replace_vars(ctx, rest) if rest else ""
                result = await self._call_value_raw(ctx, fn_name, resolved)
                if result is not None:
                    return result
        return await resolve_expression(ctx, self, expr)

    async def _call_value(self, ctx, name, arg_exprs):
        """Call a function and return its value (for ``let x = fn(...)``)."""
        resolved_args = []
        for item in arg_exprs:
            item = (item or "").strip().strip("'\"")
            resolved_args.append(await resolve_expression(ctx, self, item))

        script_fn = self._script_functions(ctx).get(name)
        if script_fn is not None:
            return await self._invoke_script_function(ctx, script_fn, resolved_args)

        func = self.registry.get(name)
        if func is None:
            return None
        args = " ".join(stringify(a) for a in resolved_args)
        return await self._invoke_registry(ctx, func, args)

    async def _call_value_raw(self, ctx, name, args: str):
        """Call a function with an already-resolved argument string."""
        script_fn = self._script_functions(ctx).get(name)
        if script_fn is not None:
            arg_values = [args] if args else []
            if script_fn.params and len(script_fn.params) > 1 and args:
                arg_values = [p.strip() for p in args.split(",") if p.strip()]
            return await self._invoke_script_function(ctx, script_fn, arg_values)

        func = self.registry.get(name)
        if func is None:
            return None
        return await self._invoke_registry(ctx, func, args)

    async def _invoke_registry(self, ctx, func, args):
        result = func(ctx, args)
        if asyncio.iscoroutine(result):
            result = await result
        return result if result is not None else getattr(ctx, "return_value", None)

    async def _invoke_script_function(self, ctx, fn: ScriptFunction, arg_values):
        if self._fn_depth >= 64:
            logger.warning("[tflow] function recursion limit reached (%s)", fn.name)
            return ""
        bound = {}
        for index, param in enumerate(fn.params):
            bound[param] = arg_values[index] if index < len(arg_values) else ""
        child = ctx.child(**bound)
        self._fn_depth += 1
        try:
            await self._run_lines(child, (fn.body or "").split("\n"))
        except FlowReturn as ret:
            return ret.value
        finally:
            self._fn_depth -= 1
        return child.return_value if child.return_value is not None else ""

    async def _run_for(self, ctx, var_name, iterable_expr, body, log_errors):
        resolved = await self._eval_rhs(ctx, iterable_expr)
        items = as_list(resolved)
        for item in items:
            ctx.set_local(var_name, item)
            # Also expose $index-friendly extras? skip — keep simple.
            try:
                await self._run_lines(ctx, body, loop_depth=1)
            except FlowContinue:
                continue
            except FlowBreak:
                break
            except FlowReturn:
                raise

    async def _run_repeat(self, ctx, count_expr, body, log_errors):
        resolved = await self._eval_rhs(ctx, count_expr)
        number = to_number(resolved)
        try:
            count = int(number) if number is not None else int(str(resolved).strip() or 0)
        except (TypeError, ValueError):
            count = 0
        count = max(0, min(count, 10_000))
        for index in range(count):
            ctx.set_local("i", index)
            ctx.set_local("index", index)
            try:
                await self._run_lines(ctx, body, loop_depth=1)
            except FlowContinue:
                continue
            except FlowBreak:
                break
            except FlowReturn:
                raise

    async def _handle_button(self, ctx, label, attrs, body):
        from .components import add_button

        label = await self.replace_vars(ctx, label or attrs.get("label", "Button"))
        custom_id = attrs.get("id") or attrs.get("custom_id") or _auto_id("btn")
        custom_id = await self.replace_vars(ctx, str(custom_id))
        style = attrs.get("style", "primary")
        code = "\n".join(body)
        add_button(ctx, label=label, custom_id=custom_id, style=style, disabled=_truthy_attr(attrs.get("disabled")))
        if code.strip():
            self._bind_component(ctx, "button", custom_id, code)

    async def _handle_select(self, ctx, attrs, body):
        from .components import add_select

        custom_id = attrs.get("id") or attrs.get("custom_id") or _auto_id("sel")
        custom_id = await self.replace_vars(ctx, str(custom_id))
        placeholder = await self.replace_vars(ctx, attrs.get("placeholder", "Select..."))
        options = []
        callback_lines = []
        for raw in body:
            stripped = raw.strip()
            if not stripped or self._is_comment(stripped):
                continue
            option = parse_option_line(stripped)
            if option is not None:
                label, value, _opt_attrs = option
                label = await self.replace_vars(ctx, label)
                value = await self.replace_vars(ctx, str(value))
                options.append((label, value))
            else:
                callback_lines.append(raw)
        add_select(ctx, custom_id=custom_id, placeholder=placeholder, options=options)
        code = "\n".join(callback_lines)
        if code.strip():
            self._bind_component(ctx, "select", custom_id, code)

    async def _handle_modal(self, ctx, title, attrs, body):
        from .components import add_modal

        title = await self.replace_vars(ctx, title or attrs.get("title", "Modal"))
        custom_id = attrs.get("id") or attrs.get("custom_id") or _auto_id("modal")
        custom_id = await self.replace_vars(ctx, str(custom_id))
        inputs = []
        callback_lines = []
        for raw in body:
            stripped = raw.strip()
            if not stripped or self._is_comment(stripped):
                continue
            field = parse_input_line(stripped)
            if field is not None:
                name, label, field_attrs = field
                name = await self.replace_vars(ctx, name)
                label = await self.replace_vars(ctx, label)
                inputs.append(
                    {
                        "name": name,
                        "label": label,
                        "placeholder": field_attrs.get("placeholder", ""),
                        "required": str(field_attrs.get("required", "true")).lower() not in ("false", "no", "0"),
                    }
                )
            else:
                callback_lines.append(raw)
        add_modal(ctx, title=title, custom_id=custom_id, inputs=inputs)
        code = "\n".join(callback_lines)
        if code.strip():
            self._bind_component(ctx, "modal", custom_id, code)

    def _bind_component(self, ctx, kind, custom_id, code):
        bot = getattr(ctx, "bot", None)
        if bot is None:
            handlers = getattr(ctx, "component_handlers", None)
            if handlers is None:
                ctx.component_handlers = {}
                handlers = ctx.component_handlers
            handlers[custom_id] = (kind, code)
            return
        bot.bind_component(kind, custom_id, code)

    async def _handle_defer(self, ctx, stripped):
        ctx.deferred = True
        interaction = getattr(ctx, "interaction", None)
        if interaction is None:
            return
        ephemeral = "ephemeral" in stripped.lower()
        try:
            response = getattr(interaction, "response", None)
            defer = getattr(response, "defer", None)
            if callable(defer):
                await defer(ephemeral=ephemeral)
        except Exception:
            logger.exception("[tflow] Failed to defer interaction")

    async def _handle_import(self, ctx, target):
        from .scripts import import_script

        await import_script(self, ctx, target)

    async def execute_line(self, ctx, line):
        """Resolve variables in ``line`` and dispatch it as a function call."""
        # Script-function call with parentheses: greet("Ada") — resolve args
        # after splitting so quoted commas survive.
        call = parse_call(line)
        if call is not None:
            name, arg_exprs = call
            script_fn = self._script_functions(ctx).get(name)
            if script_fn is not None:
                values = []
                for item in arg_exprs:
                    values.append(await self._eval_rhs(ctx, item))
                result = await self._invoke_script_function(ctx, script_fn, values)
                ctx.return_value = result
                return result

        line = await self.replace_vars(ctx, line)

        # After substitution, still allow greet(Ada) if it was not a script fn
        # (shouldn't happen) — fall through to registry.

        parts = line.split(" ", 1)
        name = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        # Bare script-function call: `greet Ada`
        script_fn = self._script_functions(ctx).get(name)
        if script_fn is not None and self.registry.get(name) is None:
            arg_values = [p for p in args.split(",") if p != ""] if args else []
            if len(script_fn.params) <= 1:
                arg_values = [args] if args else []
            result = await self._invoke_script_function(ctx, script_fn, arg_values)
            ctx.return_value = result
            return result

        func = self.registry.get(name)
        if func is None:
            bot = getattr(ctx, "bot", None)
            if bot is None or getattr(bot, "log_unknown_functions", True):
                logger.info("[tflow] Unknown function: %s", name)
            return

        result = func(ctx, args)
        if asyncio.iscoroutine(result):
            result = await result
        return result


def _auto_id(prefix: str) -> str:
    import time

    return f"{prefix}-{int(time.time() * 1000) % 10_000_000}"


def _truthy_attr(value) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on")

"""Discord interactive components for tflows scripts.

Script syntax::

    button "Click me" id="hello":
        reply You clicked the button!

    select id="color":
        option "Red" value="red"
        option "Blue" value="blue"
        reply You selected $value

    modal "Feedback" id="feedback":
        input "message" placeholder="Your feedback"
        reply Thanks: $input.message

    on button "hello":
        reply Hello!

Persistent handlers are stored on the :class:`FlowBot` and survive as long
as the process does. Inline bodies (indented under ``button``/``select``/
``modal``) are registered the same way using the component custom id.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("tflows.components")

_STYLE_MAP = {
    "primary": 1,
    "blurple": 1,
    "secondary": 2,
    "grey": 2,
    "gray": 2,
    "success": 3,
    "green": 3,
    "danger": 4,
    "red": 4,
    "link": 5,
    "url": 5,
}


class ComponentSpec:
    """A button, select, or modal waiting to be attached to the next send."""

    def __init__(self, kind: str, **fields):
        self.kind = kind
        self.fields = fields


def _ensure_pending(ctx) -> list:
    pending = getattr(ctx, "pending_components", None)
    if pending is None:
        ctx.pending_components = []
        pending = ctx.pending_components
    return pending


def add_button(ctx, *, label: str, custom_id: str, style: str = "primary", disabled: bool = False, url: str | None = None):
    _ensure_pending(ctx).append(
        ComponentSpec(
            "button",
            label=label,
            custom_id=custom_id,
            style=style,
            disabled=disabled,
            url=url,
        )
    )


def add_select(ctx, *, custom_id: str, placeholder: str = "Select...", options: list | None = None):
    _ensure_pending(ctx).append(
        ComponentSpec(
            "select",
            custom_id=custom_id,
            placeholder=placeholder,
            options=list(options or []),
        )
    )


def add_modal(ctx, *, title: str, custom_id: str, inputs: list | None = None):
    # Modals are not attached as a view; they are opened via `show_modal`.
    # Store on the bot so `show_modal id` can find the spec.
    spec = ComponentSpec("modal", title=title, custom_id=custom_id, inputs=list(inputs or []))
    bot = getattr(ctx, "bot", None)
    if bot is not None:
        bot.modals[custom_id] = spec
    ctx.pending_modal = spec
    return spec


def _discord_style(name: str):
    try:
        import discord

        mapping = {
            1: discord.ButtonStyle.primary,
            2: discord.ButtonStyle.secondary,
            3: discord.ButtonStyle.success,
            4: discord.ButtonStyle.danger,
            5: discord.ButtonStyle.link,
        }
        return mapping.get(_STYLE_MAP.get(str(name).lower(), 1), discord.ButtonStyle.primary)
    except Exception:
        return _STYLE_MAP.get(str(name).lower(), 1)


def build_view(ctx):
    """Build a discord.ui.View from pending components, or a lightweight fake.

    Returns ``None`` when there is nothing to attach. Consumes
    ``ctx.pending_components``.
    """
    pending = list(getattr(ctx, "pending_components", None) or [])
    if not pending:
        return getattr(ctx, "pending_view", None)
    ctx.pending_components = []

    try:
        import discord

        view = discord.ui.View(timeout=300)
        for spec in pending:
            if spec.kind == "button":
                style = _discord_style(spec.fields.get("style", "primary"))
                url = spec.fields.get("url")
                if url:
                    view.add_item(
                        discord.ui.Button(label=spec.fields.get("label", "Button"), style=discord.ButtonStyle.link, url=url)
                    )
                else:
                    view.add_item(
                        discord.ui.Button(
                            label=spec.fields.get("label", "Button"),
                            custom_id=spec.fields.get("custom_id"),
                            style=style,
                            disabled=bool(spec.fields.get("disabled")),
                        )
                    )
            elif spec.kind == "select":
                options = [
                    discord.SelectOption(label=str(label)[:100], value=str(value)[:100])
                    for label, value in spec.fields.get("options") or []
                ]
                if not options:
                    options = [discord.SelectOption(label="(empty)", value="empty")]
                view.add_item(
                    discord.ui.Select(
                        custom_id=spec.fields.get("custom_id"),
                        placeholder=spec.fields.get("placeholder", "Select...")[:150],
                        options=options[:25],
                    )
                )
        ctx.pending_view = view
        return view
    except Exception:
        logger.exception("[tflow] Failed to build discord View; using fake")
        fake = FakeView(pending)
        ctx.pending_view = fake
        return fake


class FakeView:
    """Stand-in view used in tests (no discord.ui available / no connection)."""

    def __init__(self, specs: list[ComponentSpec]):
        self.specs = specs
        self.children = specs
        self.timeout = None

    def __repr__(self):
        return f"<FakeView {len(self.specs)} components>"


class ComponentRegistry:
    """Maps custom_id -> (kind, code) for persistent component handlers."""

    def __init__(self):
        self.handlers: dict[str, tuple[str, str]] = {}

    def bind(self, kind: str, custom_id: str, code: str) -> None:
        self.handlers[custom_id] = (kind, code)

    def get(self, custom_id: str):
        return self.handlers.get(custom_id)

    def remove(self, custom_id: str) -> bool:
        return self.handlers.pop(custom_id, None) is not None

    def clear(self) -> None:
        self.handlers.clear()

    def unbind_kind(self, kind: str) -> None:
        for key in [k for k, (knd, _) in self.handlers.items() if knd == kind]:
            self.handlers.pop(key, None)


def interaction_value(interaction) -> str:
    """Extract the selected / submitted value from an interaction."""
    try:
        data = getattr(interaction, "data", None) or {}
        if isinstance(data, dict):
            values = data.get("values")
            if values:
                return str(values[0])
            components = data.get("components") or []
            collected = {}
            for row in components:
                for child in row.get("components", [row]):
                    cid = child.get("custom_id")
                    val = child.get("value")
                    if cid is not None:
                        collected[cid] = val
            if collected:
                return next(iter(collected.values())) or ""
        values = getattr(interaction, "values", None)
        if values:
            return str(values[0])
    except Exception:
        logger.exception("[tflow] Failed to read interaction value")
    return ""


def interaction_inputs(interaction) -> dict[str, Any]:
    """Return modal field values keyed by custom id."""
    result = {}
    try:
        data = getattr(interaction, "data", None) or {}
        if isinstance(data, dict):
            for row in data.get("components") or []:
                children = row.get("components", [row]) if isinstance(row, dict) else []
                for child in children:
                    if not isinstance(child, dict):
                        continue
                    cid = child.get("custom_id")
                    if cid is not None:
                        result[cid] = child.get("value") or ""
    except Exception:
        logger.exception("[tflow] Failed to read modal inputs")
    return result

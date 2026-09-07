"""Buttons, selects, modals, and interaction helpers."""

import pytest

from tests.fakes import FakeChannel, FakeGuild, FakeMessage, FakeUser, make_bot, make_ctx
from tflows.components import FakeView, interaction_inputs, interaction_value
from tflows.context import FlowContext


async def run(bot, code, args=""):
    message = FakeMessage(content="!t", client=bot)
    ctx = make_ctx(bot, args=args, message=message)
    await bot.engine.run(ctx, code)
    return message, ctx


def sent(message):
    return [args[0] for args, _ in message.channel.sent]


@pytest.fixture
def bot():
    return make_bot()


class FakeInteraction:
    def __init__(self, user=None, channel=None, guild=None, custom_id="", data=None, itype=None):
        self.user = user or FakeUser()
        self.channel = channel or FakeChannel()
        self.guild = guild if guild is not None else FakeGuild()
        self.custom_id = custom_id
        self.data = data if data is not None else {"custom_id": custom_id}
        self.type = itype
        self.response = type("R", (), {"deferred": False})()

        async def defer(**kwargs):
            self.response.deferred = True

        self.response.defer = defer


async def test_button_attaches_view(bot):
    message, ctx = await run(
        bot,
        'button "Click" id="hello":\n    reply clicked\nsend pick',
    )
    assert sent(message) == ["pick"]
    kwargs = message.channel.sent[0][1]
    view = kwargs.get("view")
    assert view is not None
    specs = getattr(view, "specs", None) or getattr(view, "children", [])
    assert specs
    first = specs[0]
    fields = getattr(first, "fields", None) or {}
    label = fields.get("label") or getattr(first, "label", None)
    assert label == "Click"
    assert bot.components.get("hello") is not None


async def test_button_handler_runs(bot):
    await run(bot, 'button "Click" id="hello":\n    send clicked\nsend pick')
    channel = FakeChannel()
    interaction = FakeInteraction(channel=channel, custom_id="hello")
    await bot.dispatch_interaction(interaction)
    assert [a[0] for a, _ in channel.sent] == ["clicked"]


async def test_select_options_and_value(bot):
    await run(
        bot,
        'select id="color":\n    option "Red" value="red"\n    option "Blue" value="blue"\n    send $value\nsend menu',
    )
    assert bot.components.get("color") is not None
    channel = FakeChannel()
    interaction = FakeInteraction(
        channel=channel,
        custom_id="color",
        data={"custom_id": "color", "values": ["blue"]},
    )
    await bot.dispatch_interaction(interaction)
    assert [a[0] for a, _ in channel.sent] == ["blue"]


async def test_modal_inputs(bot):
    await run(
        bot,
        'modal "Feedback" id="fb":\n    input "message" placeholder="x"\n    send $input.message',
    )
    assert "fb" in bot.modals
    channel = FakeChannel()
    interaction = FakeInteraction(
        channel=channel,
        custom_id="fb",
        data={
            "custom_id": "fb",
            "components": [{"components": [{"custom_id": "message", "value": "hi"}]}],
        },
    )
    await bot.dispatch_interaction(interaction)
    assert [a[0] for a, _ in channel.sent] == ["hi"]


async def test_defer_and_ephemeral_flags(bot):
    message, ctx = await run(bot, "ephemeral\ndefer\nsend later")
    assert ctx.ephemeral is True
    assert ctx.deferred is True
    kwargs = message.channel.sent[0][1]
    assert kwargs.get("ephemeral") is True


async def test_interaction_value_helper():
    class I:
        data = {"values": ["picked"]}
        values = None

    assert interaction_value(I()) == "picked"


async def test_interaction_inputs_helper():
    class I:
        data = {"components": [{"components": [{"custom_id": "a", "value": "1"}]}]}

    assert interaction_inputs(I()) == {"a": "1"}


async def test_unknown_interaction_is_noop(bot):
    channel = FakeChannel()
    interaction = FakeInteraction(channel=channel, custom_id="missing")
    await bot.dispatch_interaction(interaction)
    assert channel.sent == []

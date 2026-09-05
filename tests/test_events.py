"""Tests for event triggers: on join / leave / react / ..."""

import pytest

from tests.fakes import FakeChannel, FakeGuild, FakeMessage, FakeUser, make_bot
from tflows.events import EVENT_MAP, normalize_event


@pytest.fixture
def bot():
    return make_bot()


class FakeReaction:
    def __init__(self, message, emoji="👍"):
        self.message = message
        self.emoji = emoji


def test_event_map_covers_minimum():
    for name in ("join", "leave", "react"):
        assert name in EVENT_MAP
    assert EVENT_MAP["join"] == "on_member_join"
    assert EVENT_MAP["react"] == "on_reaction_add"


def test_unknown_event_rejected(bot):
    with pytest.raises(ValueError):
        bot.on_event("explosion", "send boom")


async def test_join_welcome(bot):
    channel = FakeChannel(name="welcome")
    guild = FakeGuild()
    guild.system_channel = channel
    member = FakeUser(id=7, name="Newbie")
    member.guild = guild
    bot.on_event("join", "send Welcome $user(mention)!")
    await bot.dispatch_event("on_member_join", member)
    assert channel.sent == [(("Welcome <@7>!",), {})]


async def test_on_header_verbatim(bot):
    channel = FakeChannel()
    guild = FakeGuild()
    guild.system_channel = channel
    member = FakeUser(id=8, name="Verbatim")
    member.guild = guild
    bot.on_event("join", "on join:\nsend Hi $user(name)")
    await bot.dispatch_event("on_member_join", member)
    assert channel.sent == [(("Hi Verbatim",), {})]


async def test_leave_event(bot):
    channel = FakeChannel()
    guild = FakeGuild()
    guild.system_channel = channel
    member = FakeUser(id=9, name="Leaver")
    member.guild = guild
    bot.on_event("leave", "send Bye $user(name)")
    await bot.dispatch_event("on_member_remove", member)
    assert channel.sent == [(("Bye Leaver",), {})]


async def test_react_event(bot):
    channel = FakeChannel()
    message = FakeMessage(content="hello", channel=channel, client=bot)
    user = FakeUser(id=11, name="Reactor")
    bot.on_event("react", "send $user(display) reacted!")
    await bot.dispatch_event("on_reaction_add", FakeReaction(message), user)
    assert channel.sent == [(("Reactor reacted!",), {})]


async def test_react_ignores_bots(bot):
    channel = FakeChannel()
    message = FakeMessage(content="hello", channel=channel, client=bot)
    bot_user = FakeUser(id=12, name="Bot", bot=True)
    bot.on_event("react", "send should not appear")
    await bot._tflow_on_reaction_add(FakeReaction(message), bot_user)
    assert channel.sent == []


async def test_event_with_fixed_channel(bot):
    inbox = FakeChannel(name="inbox")
    member = FakeUser(id=13, name="Fixed")
    member.guild = FakeGuild()  # no system channel configured
    bot.on_event("join", "send hello", channel=inbox)
    await bot.dispatch_event("on_member_join", member)
    assert inbox.sent == [(("hello",), {})]


async def test_remove_event(bot):
    channel = FakeChannel()
    guild = FakeGuild()
    guild.system_channel = channel
    member = FakeUser(id=14, name="X")
    member.guild = guild
    handle = bot.on_event("join", "send hi")
    assert bot.remove_event("join", handle) is True
    assert bot.remove_event("join", handle) is False
    await bot.dispatch_event("on_member_join", member)
    assert channel.sent == []


async def test_multiple_handlers_all_run(bot):
    channel = FakeChannel()
    guild = FakeGuild()
    guild.system_channel = channel
    member = FakeUser(id=15, name="Multi")
    member.guild = guild
    bot.on_event("join", "send first")
    bot.on_event("join", "send second")
    await bot.dispatch_event("on_member_join", member)
    assert [a[0] for a, _ in channel.sent] == ["first", "second"]


async def test_events_and_prefix_coexist(bot):
    channel = FakeChannel()
    guild = FakeGuild()
    guild.system_channel = channel
    member = FakeUser(id=16, name="Coexist")
    member.guild = guild
    bot.on_event("join", "send welcome")
    bot.command("ping", "send pong")
    await bot.dispatch_event("on_member_join", member)
    message = FakeMessage(content="!ping", client=bot)
    await bot.on_message(message)
    assert channel.sent == [(("welcome",), {})]
    assert message.channel.sent == [(("pong",), {})]


async def test_normalize_event_aliases():
    assert normalize_event("member_join") == "on_member_join"
    assert normalize_event("Reaction Add") == "on_reaction_add"


async def test_on_event_with_channel_id_does_not_crash(bot):
    handle = bot.on_event("join", "send hi", channel=123456)
    assert isinstance(handle, str)
    member = FakeUser(id=22, name="NoChan")
    member.guild = FakeGuild()
    await bot.dispatch_event("on_member_join", member)  # NullChannel absorbs it

"""Member/role/channel management, state scopes, event filters."""

import pytest

from tests.fakes import FakeChannel, FakeGuild, FakeMessage, FakeRole, FakeUser, make_bot, make_ctx


async def run(bot, code, args="", message=None):
    message = message or FakeMessage(content="!t", client=bot)
    ctx = make_ctx(bot, args=args, message=message)
    await bot.engine.run(ctx, code)
    return message, ctx


def sent(message):
    return [args[0] for args, _ in message.channel.sent if args]


@pytest.fixture
def bot():
    return make_bot()


async def test_role_add_remove(bot):
    guild = FakeGuild()
    guild.roles = [FakeRole("Moderator")]
    author = FakeUser()
    author.roles = []
    message = FakeMessage(content="!t", client=bot, guild=guild, author=author)
    await run(bot, "role add Moderator", message=message)
    assert any(getattr(r, "name", None) == "Moderator" for r in author.roles)
    await run(bot, "role remove Moderator", message=message)
    assert not any(getattr(r, "name", None) == "Moderator" for r in author.roles)


async def test_kick_sets_flag(bot):
    guild = FakeGuild()
    author = FakeUser()
    message = FakeMessage(content="!t", client=bot, guild=guild, author=author)
    await run(bot, "kick $user reason=spam", message=message)
    assert getattr(author, "kicked", False) is True


async def test_channel_rename(bot):
    channel = FakeChannel(name="old")
    guild = FakeGuild()
    message = FakeMessage(content="!t", client=bot, guild=guild, channel=channel)
    await run(bot, "channel rename new-name", message=message)
    assert channel.name == "new-name"


async def test_user_state_scope_isolated(bot):
    user_a = FakeUser(id=1, name="A")
    user_b = FakeUser(id=2, name="B")
    msg_a = FakeMessage(content="!t", client=bot, author=user_a)
    await run(bot, "set user.points 10", message=msg_a)
    msg_b = FakeMessage(content="!t", client=bot, author=user_b)
    message, _ = await run(bot, "get user.points fallback", message=msg_b)
    assert sent(message) == ["fallback"]
    message_a, _ = await run(bot, "get user.points", message=msg_a)
    assert sent(message_a) == ["10"]


async def test_global_state_shared_across_guilds(bot):
    guild_a = FakeGuild()
    guild_a.id = 111
    guild_b = FakeGuild()
    guild_b.id = 222
    await run(bot, "set global.flag 1", message=FakeMessage(content="!t", client=bot, guild=guild_a))
    message, _ = await run(
        bot, "get global.flag", message=FakeMessage(content="!t", client=bot, guild=guild_b)
    )
    assert sent(message) == ["1"]


async def test_unprefixed_state_still_per_guild(bot):
    guild_a = FakeGuild()
    guild_a.id = 111
    guild_b = FakeGuild()
    guild_b.id = 222
    await run(bot, "set coins 7", message=FakeMessage(content="!t", client=bot, guild=guild_a))
    message, _ = await run(
        bot, "get coins fallback", message=FakeMessage(content="!t", client=bot, guild=guild_b)
    )
    assert sent(message) == ["fallback"]


async def test_event_where_channel_filter(bot):
    inbox = FakeChannel(name="inbox")
    other = FakeChannel(name="other")
    guild = FakeGuild()
    bot.on_event("message", "send hit", where='channel == "inbox"')
    message = FakeMessage(content="hello", channel=inbox, guild=guild, client=bot)
    await bot.dispatch_event("on_message_event", message)
    assert [a[0] for a, _ in inbox.sent] == ["hit"]
    other_msg = FakeMessage(content="hello", channel=other, guild=guild, client=bot)
    await bot.dispatch_event("on_message_event", other_msg)
    assert other.sent == []


async def test_for_members_variable(bot):
    guild = FakeGuild(members=[FakeUser(1, "Ada"), FakeUser(2, "Bob")])
    message = FakeMessage(content="!t", client=bot, guild=guild)
    result, _ = await run(bot, "for name in $members:\n    send $name", message=message)
    assert sent(result) == ["Ada", "Bob"]


async def test_context_menu_registration(bot):
    cmd = bot.context_menu("user", "Inspect", "send $target")
    assert cmd is not None
    assert "Inspect" in bot.context_menus

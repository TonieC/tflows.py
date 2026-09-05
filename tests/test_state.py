"""Tests for SQLite-backed persistent per-server state."""

import pytest

from tests.fakes import FakeGuild, FakeMessage, FakeUser, make_bot, make_ctx
from tflows.state import StateStore


async def run(bot, code, args="", message=None):
    message = message or FakeMessage(content="!t", client=bot)
    ctx = make_ctx(bot, args=args, message=message)
    await bot.engine.run(ctx, code)
    return message


def sent_text(message):
    return [args[0] for args, _ in message.channel.sent if args]


@pytest.fixture
def bot():
    return make_bot()  # :memory: store via fakes.make_bot


async def test_set_and_get(bot):
    message = await run(bot, "set points 10\nget points")
    assert sent_text(message) == ["10"]


async def test_set_increment_syntax(bot):
    message = await run(bot, "set points 10\nset points +5\nget points")
    assert sent_text(message) == ["15"]


async def test_set_decrement_creates_negative(bot):
    message = await run(bot, "set points -2\nget points")
    assert sent_text(message) == ["-2"]


async def test_incr_default_and_amount(bot):
    message = await run(bot, "incr hits\nincr hits 4\nget hits")
    assert sent_text(message) == ["5"]


async def test_del_removes_key(bot):
    message = await run(bot, "set k v\ndel k\nget k fallback")
    assert sent_text(message) == ["fallback"]


async def test_get_missing_key_sends_nothing(bot):
    message = await run(bot, "get never_set")
    assert sent_text(message) == []


async def test_get_with_fallback(bot):
    message = await run(bot, "get never_set hello")
    assert sent_text(message) == ["hello"]


async def test_get_variable_inline(bot):
    message = await run(bot, "set mood happy\nsend I am $get(mood) today")
    assert sent_text(message) == ["I am happy today"]


async def test_get_variable_default(bot):
    message = await run(bot, "send x$get(missing, dflt)y")
    assert sent_text(message) == ["xdflty"]


async def test_dynamic_key_with_user(bot):
    message = await run(bot, "set points[$user] +10\nget points[$user]")
    assert sent_text(message) == ["10"]


async def test_state_isolated_per_guild(bot):
    guild_a = FakeGuild()
    guild_a.id = 111
    guild_b = FakeGuild()
    guild_b.id = 222
    await run(bot, "set coins 7", message=FakeMessage(content="!t", client=bot, guild=guild_a))
    message_b = await run(bot, "get coins fallback", message=FakeMessage(content="!t", client=bot, guild=guild_b))
    assert sent_text(message_b) == ["fallback"]
    message_a = await run(bot, "get coins", message=FakeMessage(content="!t", client=bot, guild=guild_a))
    assert sent_text(message_a) == ["7"]


async def test_counters_strings_booleans(tmp_path):
    store = StateStore(str(tmp_path / "s.db"))
    await store.set("g", "counter", 3)
    assert await store.get("g", "counter") == "3"
    assert await store.incr("g", "counter", 2) == 5
    await store.set("g", "flag", True)
    assert await store.get("g", "flag") == "true"
    await store.set("g", "name", "bob")
    assert await store.get("g", "name") == "bob"
    assert await store.delete("g", "name") is True
    assert await store.get("g", "name") is None
    store.close()


async def test_state_survives_restart(tmp_path):
    path = str(tmp_path / "persist.db")
    store = StateStore(path)
    await store.set("999", "points", "42")
    store.close()
    reopened = StateStore(path)
    try:
        assert await reopened.get("999", "points") == "42"
    finally:
        reopened.close()


async def test_concurrent_increments_are_safe(bot):
    import asyncio

    store = bot.state
    await asyncio.gather(*[store.incr("g", "n", 1) for _ in range(25)])
    assert await store.get("g", "n") == "25"


async def test_state_disabled_reports_useful_error():
    bot = make_bot(state_path=None)
    message = FakeMessage(content="!t", client=bot)
    ctx = make_ctx(bot, message=message)
    with pytest.raises(RuntimeError):
        await bot.engine.registry.get("set")(ctx, "k v")


async def test_state_in_prefix_command(bot):
    bot.command("add", "set score[$user] +5\nget score[$user]")
    message = FakeMessage(content="!add", client=bot)
    await bot.on_message(message)
    assert sent_text(message) == ["5"]
    message2 = FakeMessage(content="!add", client=bot, author=FakeUser(id=777, name="Other"))
    await bot.on_message(message2)
    assert sent_text(message2) == ["5"]  # per-user key, fresh counter

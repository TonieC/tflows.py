import pytest

from tests.fakes import FakeMessage, make_bot, make_ctx
from tflows.context import FlowContext


@pytest.fixture
def bot():
    return make_bot()


async def run_script(bot, code, args="", message=None):
    message = message or FakeMessage(content="!t", client=bot)
    ctx = FlowContext(message=message, bot=bot, command_name="t", args=args)
    await bot.engine.run(ctx, code)
    return message


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------
async def test_send_function(bot):
    message = await run_script(bot, "send hello")
    assert message.channel.sent == [(("hello",), {})]


async def test_send_function_empty_args_no_crash(bot):
    message = await run_script(bot, "send")
    assert message.channel.sent == []


async def test_reply_function(bot):
    message = await run_script(bot, "reply hi")
    assert message.replied == [(("hi",), {})]


async def test_react_function(bot):
    message = await run_script(bot, "react :thumbsup: :tada:")
    assert message.reactions == [":thumbsup:", ":tada:"]


async def test_delete_function(bot):
    message = await run_script(bot, "delete")
    assert message.deleted is True


async def test_wait_function(bot):
    message = await run_script(bot, "wait 0\nsend after")
    assert message.channel.sent == [(("after",), {})]


async def test_wait_function_invalid_duration_no_crash(bot):
    await run_script(bot, "wait not-a-number")


async def test_clear_function_with_permission(bot):
    message = await run_script(bot, "clear 5")
    assert message.deleted is True
    assert message.channel.purged == [5]


async def test_clear_function_requires_permission(bot):
    message = FakeMessage(content="!t", client=bot)
    message.channel.permissions_for = lambda user: type("P", (), {"manage_messages": False})()
    await run_script(bot, "clear 5", message=message)
    assert message.deleted is False
    assert message.channel.sent != []


async def test_clear_function_clamps_count(bot):
    message = await run_script(bot, "clear 9999")
    assert message.channel.purged == [100]


# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------
async def test_ping_var(bot):
    result = await bot.engine.replace_vars(make_ctx(bot), "pong $ping")
    assert result.endswith("ms")


async def test_time_var(bot):
    ctx = make_ctx(bot)
    full = await bot.engine.replace_vars(ctx, "$time")
    assert full == "" or len(full) >= 5
    date_only = await bot.engine.replace_vars(ctx, "$time(notime)")
    assert len(date_only) == 10


async def test_uptime_var(bot):
    ctx = make_ctx(bot)
    default = await bot.engine.replace_vars(ctx, "$uptime")
    assert default.endswith("s")
    seconds = await bot.engine.replace_vars(ctx, "$uptime(seconds)")
    assert seconds.isdigit()
    clock = await bot.engine.replace_vars(ctx, "$uptime(clock)")
    assert len(clock.split(":")) == 3


async def test_server_var(bot):
    ctx = make_ctx(bot)
    assert await bot.engine.replace_vars(ctx, "$server") == "Test Guild"
    assert await bot.engine.replace_vars(ctx, "$server(id)") == "999"
    assert await bot.engine.replace_vars(ctx, "$server(boost)") == "3"
    assert await bot.engine.replace_vars(ctx, "$server(boostlvl)") == "2"
    assert await bot.engine.replace_vars(ctx, "$server(members)") == "10"


async def test_guild_var_alias(bot):
    ctx = make_ctx(bot)
    assert await bot.engine.replace_vars(ctx, "$guild(name)") == "Test Guild"


async def test_membercount_var(bot):
    ctx = make_ctx(bot)
    assert await bot.engine.replace_vars(ctx, "$membercount") == "10"
    assert await bot.engine.replace_vars(ctx, "$membercount(all)") == "10"
    assert await bot.engine.replace_vars(ctx, "$membercount(bots)") == "0"


async def test_user_var(bot):
    ctx = make_ctx(bot)
    assert await bot.engine.replace_vars(ctx, "$user") == "Tester"
    assert await bot.engine.replace_vars(ctx, "$user(name)") == "Tester"
    assert await bot.engine.replace_vars(ctx, "$user(id)") == "123"
    assert await bot.engine.replace_vars(ctx, "$user(mention)") == "<@123>"
    assert await bot.engine.replace_vars(ctx, "$user(avatar)") == "https://example.com/123.png"
    assert await bot.engine.replace_vars(ctx, "$user(bot)") == "false"


async def test_author_var_alias(bot):
    ctx = make_ctx(bot)
    assert await bot.engine.replace_vars(ctx, "$author(id)") == "123"


async def test_avatar_and_image_vars(bot):
    ctx = make_ctx(bot)
    assert await bot.engine.replace_vars(ctx, "$avatar") == "https://example.com/123.png"
    assert await bot.engine.replace_vars(ctx, "$image") == "https://example.com/123.png"


async def test_channel_var(bot):
    ctx = make_ctx(bot)
    assert await bot.engine.replace_vars(ctx, "$channel") == "general"
    assert await bot.engine.replace_vars(ctx, "$channel(id)") == "555"
    assert await bot.engine.replace_vars(ctx, "$channel(mention)") == "<#555>"
    assert await bot.engine.replace_vars(ctx, "$channel(topic)") == "General discussion"
    assert await bot.engine.replace_vars(ctx, "$channel(nsfw)") == "false"


async def test_bot_var(bot):
    ctx = make_ctx(bot)
    assert await bot.engine.replace_vars(ctx, "$bot(name)") == "TestBot"
    assert await bot.engine.replace_vars(ctx, "$bot(id)") == "1"
    assert await bot.engine.replace_vars(ctx, "$bot(mention)") == "<@1>"
    assert (await bot.engine.replace_vars(ctx, "$bot(ping)")).endswith("ms")


async def test_args_vars(bot):
    ctx = make_ctx(bot, args="one two three")
    assert await bot.engine.replace_vars(ctx, "$args") == "one two three"
    assert await bot.engine.replace_vars(ctx, "$arg(0)") == "one"
    assert await bot.engine.replace_vars(ctx, "$arg(1)") == "two"
    assert await bot.engine.replace_vars(ctx, "$arg(2)") == "three"
    assert await bot.engine.replace_vars(ctx, "$argcount") == "3"
    assert await bot.engine.replace_vars(ctx, "$arg(-1)") == "three"
    assert await bot.engine.replace_vars(ctx, "$arg(0:2)") == "one two"
    assert await bot.engine.replace_vars(ctx, "$arg(9)") == ""


async def test_args_vars_empty(bot):
    ctx = make_ctx(bot, args="")
    assert await bot.engine.replace_vars(ctx, "$args") == ""
    assert await bot.engine.replace_vars(ctx, "$argcount") == "0"


async def test_prefix_and_command_vars(bot):
    ctx = make_ctx(bot, command_name="greet")
    assert await bot.engine.replace_vars(ctx, "$prefix") == "!"
    assert await bot.engine.replace_vars(ctx, "$command") == "greet"


async def test_random_var(bot):
    ctx = make_ctx(bot)
    value = await bot.engine.replace_vars(ctx, "$random(1, 6)")
    assert 1 <= int(value) <= 6
    assert (await bot.engine.replace_vars(ctx, "$random(5, 5)")) == "5"


async def test_id_var(bot):
    ctx = make_ctx(bot)
    assert await bot.engine.replace_vars(ctx, "$id") == "123"

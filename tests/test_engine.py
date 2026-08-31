import pytest

from tests.fakes import FakeMessage, make_bot, make_ctx
from tflows import FunctionRegistry
from tflows.context import FlowContext
from tflows.engine import Engine
from tflows.loader import load_function


@pytest.fixture
def bot():
    return make_bot()


async def test_replace_vars_basic(bot):
    ctx = make_ctx(bot, args="hello world")
    result = await bot.engine.replace_vars(ctx, "$args and $arg(1)")
    assert result == "hello world and world"


async def test_replace_vars_unknown_left_untouched(bot):
    ctx = make_ctx(bot)
    result = await bot.engine.replace_vars(ctx, "keep $unknown here")
    assert result == "keep $unknown here"


async def test_replace_vars_multiple_on_same_line(bot):
    ctx = make_ctx(bot, args="a b c")
    result = await bot.engine.replace_vars(ctx, "$arg(0)-$arg(1)-$arg(2)")
    assert result == "a-b-c"


async def test_replace_vars_with_async_var(bot):
    ctx = make_ctx(bot)

    async def async_var(ctx, args):
        return "async-value"

    bot.engine.registry.register_var("asyncvar", async_var)
    try:
        result = await bot.engine.replace_vars(ctx, "got $asyncvar")
    finally:
        bot.engine.registry.unregister_var("asyncvar")
    assert result == "got async-value"


async def test_replace_vars_none_result_empty(bot):
    ctx = make_ctx(bot)
    bot.engine.registry.register_var("nil", lambda ctx, args: None)
    try:
        result = await bot.engine.replace_vars(ctx, "[$nil]")
    finally:
        bot.engine.registry.unregister_var("nil")
    assert result == "[]"


async def test_run_send(bot):
    message = FakeMessage(content="!t")
    ctx = FlowContext(message=message, bot=bot)
    await bot.engine.run(ctx, "send Hello world")
    assert message.channel.sent == [(("Hello world",), {})]


async def test_run_multiline(bot):
    message = FakeMessage(content="!t")
    ctx = FlowContext(message=message, bot=bot)
    await bot.engine.run(ctx, "send one\nsend two")
    sent = [args[0] for args, _ in message.channel.sent]
    assert sent == ["one", "two"]


async def test_run_ignores_comments_and_blank_lines(bot):
    message = FakeMessage(content="!t")
    ctx = FlowContext(message=message, bot=bot)
    await bot.engine.run(
        ctx,
        "\n// a comment\n# another\n-- dashed\n\nsend only-this\n",
    )
    sent = [args[0] for args, _ in message.channel.sent]
    assert sent == ["only-this"]


async def test_run_unknown_function_logged(bot, caplog):
    message = FakeMessage(content="!t")
    ctx = FlowContext(message=message, bot=bot)
    with caplog.at_level("INFO", logger="tflows.engine"):
        await bot.engine.run(ctx, "not_a_function foo")
    assert any("Unknown function: not_a_function" in r.message for r in caplog.records)


async def test_run_function_error_logged_not_raised(bot, caplog):
    @bot.engine.registry.register("boom")
    async def boom(ctx, args):
        raise RuntimeError("exploded")

    try:
        message = FakeMessage(content="!t")
        ctx = FlowContext(message=message, bot=bot)
        with caplog.at_level("ERROR", logger="tflows.engine"):
            await bot.engine.run(ctx, "boom")
        assert any("Error in line" in r.message for r in caplog.records)
    finally:
        bot.engine.registry.unregister("boom")


async def test_run_does_not_swallow_when_log_errors_false(bot, caplog):
    quiet = make_bot(log_errors=False)

    @quiet.engine.registry.register("boom")
    async def boom(ctx, args):
        raise RuntimeError("exploded")

    try:
        message = FakeMessage(content="!t")
        ctx = FlowContext(message=message, bot=quiet)
        with caplog.at_level("ERROR", logger="tflows.engine"):
            await quiet.engine.run(ctx, "boom")
        assert not any("Error in line" in r.message for r in caplog.records)
    finally:
        quiet.engine.registry.unregister("boom")


async def test_run_accepts_raw_message(bot):
    # Backward compatibility: engine.run(message, code) works without FlowContext.
    message = FakeMessage(content="!t")
    await bot.engine.run(message, "send raw")
    assert message.channel.sent == [(("raw",), {})]


async def test_run_embed_block(bot):
    message = FakeMessage(content="!t")
    ctx = FlowContext(message=message, bot=bot)
    code = "embed\n$title[Hello]\n$desc[World]\n$footer[Bye]\n$color[red]\nendembed"
    await bot.engine.run(ctx, code)
    embed = message.channel.sent[0][1]["embed"]
    assert embed.title == "Hello"
    assert embed.description == "World"
    assert embed.footer.text == "Bye"
    assert embed.color.value == 0xE74C3C


async def test_run_embed_block_resolves_vars(bot):
    message = FakeMessage(content="!t")
    ctx = FlowContext(message=message, bot=bot, args="alice")
    code = "embed\n$title[Hi $user(display)]\n$desc[Args: $args]\nendembed"
    await bot.engine.run(ctx, code)
    embed = message.channel.sent[0][1]["embed"]
    assert embed.title == "Hi Tester"
    assert embed.description == "Args: alice"


async def test_run_embed_block_plain_text_fallback(bot):
    message = FakeMessage(content="!t")
    ctx = FlowContext(message=message, bot=bot)
    code = "embed\nJust some description text\nendembed"
    await bot.engine.run(ctx, code)
    embed = message.channel.sent[0][1]["embed"]
    assert embed.description == "Just some description text"


async def test_run_embed_block_thumbnail_image_timestamp(bot):
    message = FakeMessage(content="!t")
    ctx = FlowContext(message=message, bot=bot)
    code = (
        "embed\n"
        "$thumbnail[https://example.com/t.png]\n"
        "$image[https://example.com/i.png]\n"
        "$timestamp[now]\n"
        "endembed"
    )
    await bot.engine.run(ctx, code)
    embed = message.channel.sent[0][1]["embed"]
    assert embed.thumbnail.url == "https://example.com/t.png"
    assert embed.image.url == "https://example.com/i.png"
    assert embed.timestamp == message.created_at


async def test_execute_line_directly(bot):
    message = FakeMessage(content="!t")
    ctx = FlowContext(message=message, bot=bot)
    await bot.engine.execute_line(ctx, "send direct")
    assert message.channel.sent == [(("direct",), {})]


async def test_standalone_engine_with_fresh_registry():
    registry = FunctionRegistry()
    load_function(registry)
    engine = Engine(registry)
    message = FakeMessage(content="!t")
    await engine.run(message, "send standalone")
    assert message.channel.sent == [(("standalone",), {})]

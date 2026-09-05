"""Tests for tflows conditionals: if / elif / else / endif."""

import pytest

from tests.fakes import FakeMessage, make_bot, make_ctx


async def run(bot, code, args=""):
    message = FakeMessage(content="!t", client=bot)
    ctx = make_ctx(bot, args=args, message=message)
    await bot.engine.run(ctx, code)
    return message


def sent(message):
    return [args[0] for args, _ in message.channel.sent]


@pytest.fixture
def bot():
    return make_bot()


async def test_if_true_branch(bot):
    message = await run(bot, "if $argcount > 0:\n    send yes", args="x")
    assert sent(message) == ["yes"]


async def test_if_false_branch_sends_nothing(bot):
    message = await run(bot, "if $argcount > 5:\n    send yes")
    assert sent(message) == []


async def test_if_else(bot):
    code = "if $argcount > 1:\n    send many\nelse:\n    send few"
    assert sent(await run(bot, code, args="a b")) == ["many"]
    assert sent(await run(bot, code, args="a")) == ["few"]
    assert sent(await run(bot, code, args="")) == ["few"]


async def test_elif_chain(bot):
    code = (
        "if $argcount == 0:\n    send none\n"
        "elif $argcount == 1:\n    send one\n"
        "else:\n    send many"
    )
    assert sent(await run(bot, code, args="")) == ["none"]
    assert sent(await run(bot, code, args="a")) == ["one"]
    assert sent(await run(bot, code, args="a b")) == ["many"]


async def test_endif_terminator(bot):
    code = "if $argcount > 0:\n    send inside\nendif\nsend after"
    assert sent(await run(bot, code, args="x")) == ["inside", "after"]
    assert sent(await run(bot, code, args="")) == ["after"]


async def test_dedent_closes_block(bot):
    code = "if $argcount > 0:\n    send inside\nsend after"
    assert sent(await run(bot, code, args="x")) == ["inside", "after"]
    assert sent(await run(bot, code, args="")) == ["after"]


async def test_nested_conditionals(bot):
    code = (
        "if $argcount > 0:\n"
        "    if $arg(0) == admin:\n"
        "        send super\n"
        "    else:\n"
        "        send regular\n"
        "    endif\n"
        "else:\n"
        "    send none"
    )
    assert sent(await run(bot, code, args="admin")) == ["super"]
    assert sent(await run(bot, code, args="bob")) == ["regular"]
    assert sent(await run(bot, code, args="")) == ["none"]


async def test_comparison_operators(bot):
    assert sent(await run(bot, "if 2 > 1:\n    send yes")) == ["yes"]
    assert sent(await run(bot, "if 1 > 2:\n    send yes")) == []
    assert sent(await run(bot, "if 2 >= 2:\n    send yes")) == ["yes"]
    assert sent(await run(bot, "if 1 <= 2:\n    send yes")) == ["yes"]
    assert sent(await run(bot, "if 1 != 2:\n    send yes")) == ["yes"]
    assert sent(await run(bot, "if 2 != 2:\n    send yes")) == []


async def test_string_equality_and_quotes(bot):
    assert sent(await run(bot, 'if hello == hello:\n    send yes')) == ["yes"]
    assert sent(await run(bot, 'if "a b" == "a b":\n    send yes')) == ["yes"]
    assert sent(await run(bot, 'if hello == world:\n    send yes')) == []


async def test_user_variable_condition(bot):
    assert sent(await run(bot, "if $user == Tester:\n    send matched")) == ["matched"]
    assert sent(await run(bot, "if $user == Nobody:\n    send matched")) == []


async def test_and_or_not(bot):
    assert sent(await run(bot, "if 1 == 1 and 2 == 2:\n    send yes")) == ["yes"]
    assert sent(await run(bot, "if 1 == 1 and 2 == 3:\n    send yes")) == []
    assert sent(await run(bot, "if 1 == 2 or 2 == 2:\n    send yes")) == ["yes"]
    assert sent(await run(bot, "if not 1 == 2:\n    send yes")) == ["yes"]
    assert sent(await run(bot, "if not 1 == 1:\n    send yes")) == []


async def test_contains_operator(bot):
    assert sent(await run(bot, "if hello world contains world:\n    send yes")) == ["yes"]
    assert sent(await run(bot, "if hello contains world:\n    send yes")) == []


async def test_bare_truthiness(bot):
    assert sent(await run(bot, "if true:\n    send yes")) == ["yes"]
    assert sent(await run(bot, "if false:\n    send yes")) == []
    assert sent(await run(bot, "if 0:\n    send yes")) == []
    assert sent(await run(bot, "if something:\n    send yes")) == ["yes"]


async def test_inactive_branch_does_not_execute(bot):
    # Same-level style without endif: everything after belongs to the branch.
    message = await run(bot, "if 1 == 2:\nsend hidden\nsend shown")
    assert sent(message) == []
    message = await run(bot, "if 1 == 2:\n    send hidden\nendif\nsend shown")
    assert sent(message) == ["shown"]


async def test_empty_condition_does_not_crash(bot, caplog):
    message = await run(bot, "if:\n    send hidden\nendif\nsend shown")
    assert sent(message) == ["shown"]


async def test_stray_else_does_not_crash(bot, caplog):
    # A stray `else` is ignored with a warning; following code runs normally.
    message = await run(bot, "else:\n    send x")
    assert sent(message) == ["x"]


async def test_conditionals_inside_prefix_command(bot):
    bot.command("check", "if $argcount > 1:\n    reply many\nelse:\n    reply few")
    message = FakeMessage(content="!check a b", client=bot)
    await bot.on_message(message)
    assert message.replied == [(("many",), {})]
    message = FakeMessage(content="!check a", client=bot)
    await bot.on_message(message)
    assert message.replied == [(("few",), {})]


async def test_embed_inside_conditional(bot):
    code = "if $argcount > 0:\n    embed\n    $title[Hi]\n    endembed\nendif"
    message = await run(bot, code, args="x")
    assert message.channel.sent[0][1]["embed"].title == "Hi"
    message = await run(bot, code, args="")
    assert message.channel.sent == []

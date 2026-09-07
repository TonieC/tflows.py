"""Locals, expressions, loops, script functions, and control flow."""

import pytest

from tests.fakes import FakeMessage, make_bot, make_ctx


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


async def test_let_and_interpolate(bot):
    message, ctx = await run(bot, "let name = Ada\nsend Hello $name")
    assert sent(message) == ["Hello Ada"]
    assert ctx.get_local("name").value == "Ada"


async def test_let_arithmetic(bot):
    message, _ = await run(bot, "let n = 1 + 2 * 3\nsend $n")
    assert sent(message) == ["7"]


async def test_reassignment(bot):
    message, _ = await run(bot, "let n = 1\nn = n + 4\nsend $n")
    assert sent(message) == ["5"]


async def test_let_string_concat(bot):
    message, _ = await run(bot, 'let greet = "Hi " + $user(name)\nsend $greet')
    assert sent(message) == ["Hi Tester"]


async def test_unknown_variable_left_untouched(bot):
    message, _ = await run(bot, "send keep $nope here")
    assert sent(message) == ["keep $nope here"]


async def test_for_comma_list(bot):
    message, _ = await run(bot, "for item in a, b, c:\n    send $item")
    assert sent(message) == ["a", "b", "c"]


async def test_for_empty_iterable(bot):
    message, _ = await run(bot, 'let items = ""\nfor item in items:\n    send nope\nsend after')
    assert sent(message) == ["after"]


async def test_repeat_sets_index(bot):
    message, _ = await run(bot, "repeat 3:\n    send $i")
    assert sent(message) == ["0", "1", "2"]


async def test_repeat_zero(bot):
    message, _ = await run(bot, "repeat 0:\n    send nope\nsend after")
    assert sent(message) == ["after"]


async def test_break_leaves_loop(bot):
    code = (
        "for item in a, b, c:\n"
        "    if $item == b:\n"
        "        break\n"
        "    send $item\n"
        "send done"
    )
    message, _ = await run(bot, code)
    assert sent(message) == ["a", "done"]


async def test_continue_skips_rest(bot):
    code = (
        "for item in a, b, c:\n"
        "    if $item == b:\n"
        "        continue\n"
        "    send $item"
    )
    message, _ = await run(bot, code)
    assert sent(message) == ["a", "c"]


async def test_nested_loops(bot):
    code = (
        "for x in 1, 2:\n"
        "    for y in a, b:\n"
        "        send $x$y"
    )
    message, _ = await run(bot, code)
    assert sent(message) == ["1a", "1b", "2a", "2b"]


async def test_function_definition_and_call(bot):
    code = (
        "function greet(name):\n"
        "    return Hello $name\n"
        "send $greet(Ada)"
    )
    message, _ = await run(bot, code)
    assert sent(message) == ["Hello Ada"]


async def test_function_call_as_statement(bot):
    code = (
        "function shout(text):\n"
        "    send $text\n"
        "shout(hi)"
    )
    message, _ = await run(bot, code)
    assert sent(message) == ["hi"]


async def test_function_default_empty_arg(bot):
    code = (
        "function ping(name):\n"
        "    return pong-$name\n"
        "send $ping()"
    )
    message, _ = await run(bot, code)
    assert sent(message) == ["pong-"]


async def test_function_locals_isolated(bot):
    code = (
        "let name = outer\n"
        "function inner(name):\n"
        "    send $name\n"
        "inner(inner)\n"
        "send $name"
    )
    message, _ = await run(bot, code)
    assert sent(message) == ["inner", "outer"]


async def test_return_from_script(bot):
    message, ctx = await run(bot, "send one\nreturn 7\nsend two")
    assert sent(message) == ["one"]
    assert ctx.return_value == 7 or ctx.return_value == "7"


async def test_if_with_local(bot):
    code = (
        "let n = 3\n"
        "if n > 2:\n"
        "    send yes\n"
        "else:\n"
        "    send no"
    )
    message, _ = await run(bot, code)
    assert sent(message) == ["yes"]


async def test_let_json_path_access(bot):
    code = (
        'let data = json.parse {"name": "Ada", "n": 1}\n'
        "send $data[name]"
    )
    message, _ = await run(bot, code)
    assert sent(message) == ["Ada"]


async def test_function_interpolated_in_middle_of_line(bot):
    code = (
        "function f(x):\n"
        "    return $x\n"
        "send start-$f(1)-end"
    )
    message, _ = await run(bot, code)
    assert sent(message) == ["start-1-end"]


async def test_existing_send_still_works(bot):
    message, _ = await run(bot, "send Hello world")
    assert sent(message) == ["Hello world"]


async def test_args_still_work_with_locals(bot):
    message, _ = await run(bot, "let x = $arg(0)\nsend $x", args="alpha")
    assert sent(message) == ["alpha"]

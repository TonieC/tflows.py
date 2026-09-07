"""Script import sandbox, tflows check CLI, load/reload."""

import os

import pytest

from tests.fakes import FakeChannel, FakeGuild, FakeMessage, FakeUser, make_bot, make_ctx
from tflows.cli import main
from tflows.diagnostics import check_source
from tflows.scripts import ImportError_, import_script


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


async def test_import_loads_function(bot, tmp_path):
    helper = tmp_path / "helper.flow"
    helper.write_text("function greet(name):\n    return Hello $name\n", encoding="utf-8")
    bot.script_root = str(tmp_path)
    bot.engine.script_root = str(tmp_path)
    message, _ = await run(bot, "import helper.flow\nsend $greet(Ada)")
    assert sent(message) == ["Hello Ada"]


async def test_import_rejects_parent_path(bot, tmp_path):
    bot.script_root = str(tmp_path)
    bot.engine.script_root = str(tmp_path)
    ctx = make_ctx(bot)
    with pytest.raises(ImportError_):
        await import_script(bot.engine, ctx, "../secret.flow")


async def test_import_rejects_remote(bot, tmp_path):
    bot.script_root = str(tmp_path)
    bot.engine.script_root = str(tmp_path)
    ctx = make_ctx(bot)
    with pytest.raises(ImportError_):
        await import_script(bot.engine, ctx, "https://evil.example/x.flow")


async def test_import_duplicate_skipped(bot, tmp_path):
    helper = tmp_path / "once.flow"
    helper.write_text("let imported = 1\n", encoding="utf-8")
    bot.script_root = str(tmp_path)
    bot.engine.script_root = str(tmp_path)
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    await import_script(bot.engine, ctx, "once.flow")
    await import_script(bot.engine, ctx, "once.flow")
    assert list(bot.engine._loaded) == [str(helper.resolve())]


async def test_circular_import(bot, tmp_path):
    a = tmp_path / "a.flow"
    b = tmp_path / "b.flow"
    a.write_text("import b.flow\n", encoding="utf-8")
    b.write_text("import a.flow\n", encoding="utf-8")
    bot.script_root = str(tmp_path)
    bot.engine.script_root = str(tmp_path)
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    with pytest.raises(ImportError_):
        await import_script(bot.engine, ctx, "a.flow")


def test_check_unclosed_if():
    diags = check_source("if true:\n    send hi")
    assert any(d.severity == "error" and "unclosed if" in d.message for d in diags)


def test_check_break_outside_loop():
    diags = check_source("break")
    assert any("outside of a loop" in d.message for d in diags)


def test_check_ok_script():
    diags = check_source("if 1 == 1:\n    send hi\nendif")
    errors = [d for d in diags if d.severity == "error"]
    assert errors == []


def test_cli_check_file(tmp_path, capsys):
    script = tmp_path / "bot.flow"
    script.write_text("if true:\n    send hi\n", encoding="utf-8")
    code = main(["check", str(script)])
    captured = capsys.readouterr()
    assert code == 1
    assert "unclosed if" in captured.out


def test_cli_version(capsys):
    code = main(["--version"])
    assert code == 0
    assert capsys.readouterr().out.strip()


async def test_bot_load_and_reload(bot, tmp_path):
    script = tmp_path / "cmd.flow"
    script.write_text("command ping:\n    send pong\n", encoding="utf-8")
    bot.load(str(script))
    message = FakeMessage(content="!ping", client=bot)
    await bot.on_message(message)
    assert sent(message) == ["pong"]
    script.write_text("command ping:\n    send pong2\n", encoding="utf-8")
    errors = await bot.reload(str(script))
    assert errors == []
    message2 = FakeMessage(content="!ping", client=bot)
    await bot.on_message(message2)
    assert sent(message2) == ["pong2"]


async def test_reload_keeps_previous_on_syntax_error(bot, tmp_path):
    script = tmp_path / "cmd.flow"
    script.write_text("command ping:\n    send pong\n", encoding="utf-8")
    bot.load(str(script))
    script.write_text("if true:\n    send hi\n", encoding="utf-8")
    errors = await bot.reload(str(script))
    assert errors
    message = FakeMessage(content="!ping", client=bot)
    await bot.on_message(message)
    assert sent(message) == ["pong"]


async def test_load_event_from_file(bot, tmp_path):
    script = tmp_path / "ev.flow"
    script.write_text("on join:\n    send Welcome $user(name)\n", encoding="utf-8")
    bot.load(str(script))
    channel = FakeChannel()
    guild = FakeGuild()
    guild.system_channel = channel
    member = FakeUser(id=3, name="Ada")
    member.guild = guild
    await bot.dispatch_event("on_member_join", member)
    assert [a[0] for a, _ in channel.sent] == ["Welcome Ada"]

"""Tests for mixed-unit durations, after/switch, config, and FlowBot knobs."""

import pytest

from tests.fakes import FakeMessage, make_bot, make_ctx
from tflows.guards import parse_cooldown
from tflows.scheduler import parse_every_header
from tflows.utils import format_duration, parse_duration


async def run(bot, code, args="", message=None):
    message = message or FakeMessage(content="!t", client=bot)
    ctx = make_ctx(bot, args=args, message=message)
    await bot.engine.run(ctx, code)
    return message, ctx


def sent(message):
    return [args[0] for args, _ in message.channel.sent if args]


def test_parse_duration_plain_seconds():
    assert parse_duration("5") == 5
    assert parse_duration(5) == 5
    assert parse_duration("5s") == 5


def test_parse_duration_mixed_units():
    assert parse_duration("1h30m") == 5400
    assert parse_duration("1h 30m") == 5400
    assert parse_duration("1 hour 30 minutes") == 5400
    assert parse_duration("500ms") == 0.5
    assert parse_duration("2m 15s") == 135
    assert parse_duration("1d 2h") == 93600
    assert parse_duration("1 week") == 604800


def test_parse_duration_invalid():
    assert parse_duration("banana") is None
    assert parse_duration("") is None
    assert parse_duration(None) is None
    assert parse_duration("1h banana") is None


def test_format_duration():
    assert format_duration(0) == "0s"
    assert format_duration(0.5) == "500ms"
    assert format_duration(90) == "1m 30s"
    assert format_duration(5400) == "1h 30m"


def test_cooldown_mixed_duration():
    assert parse_cooldown("cooldown 1h 30m per user") == (5400, "user")
    assert parse_cooldown("cooldown 500ms") == (0.5, "user")
    assert parse_cooldown("cooldown 2 minutes per guild") == (120, "guild")


def test_every_header_mixed_duration():
    assert parse_every_header("every 1h 30m:") == 5400
    assert parse_every_header("every 90s") == 90


async def test_wait_mixed_duration(monkeypatch):
    bot = make_bot()
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr("tflows.function.wait.asyncio.sleep", fake_sleep)
    await run(bot, "wait 1s 500ms")
    assert slept == [1.5]


async def test_wait_respects_max_wait(monkeypatch):
    bot = make_bot(max_wait=2)
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr("tflows.function.wait.asyncio.sleep", fake_sleep)
    await run(bot, "wait 1h")
    assert slept == [2]


async def test_switch_matches_case():
    bot = make_bot()
    message, _ = await run(
        bot,
        "switch $arg(0):\n    case ping:\n        send pong\n    case hi:\n        send hello\n    default:\n        send other",
        args="hi",
    )
    assert sent(message) == ["hello"]


async def test_switch_default():
    bot = make_bot()
    message, _ = await run(
        bot,
        "switch $arg(0):\n    case ping:\n        send pong\n    default:\n        send other",
        args="nope",
    )
    assert sent(message) == ["other"]


async def test_after_zero_runs_inline():
    bot = make_bot()
    message, _ = await run(bot, "after 0s:\n    send later\nsend now")
    assert sent(message) == ["later", "now"]


async def test_config_from_constructor():
    bot = make_bot(config={"theme": "dark", "owner": "Ada"})
    message, _ = await run(bot, "send $config(theme) $config(owner)")
    assert sent(message) == ["dark Ada"]


async def test_config_set_and_read():
    bot = make_bot()
    message, _ = await run(bot, "config theme neon\nsend $config(theme)")
    assert sent(message) == ["neon"]


async def test_choose_picks_from_list(monkeypatch):
    bot = make_bot()
    monkeypatch.setattr("tflows.function.util.random.choice", lambda items: items[1])
    message, _ = await run(bot, "send $choose(red, green, blue)")
    assert sent(message) == ["green"]


async def test_exists_and_keys():
    bot = make_bot()
    message, _ = await run(
        bot,
        "set points 10\nsend $exists(points)\nsend $exists(missing)\nsend $keys()",
    )
    assert sent(message) == ["true", "false", "points"]


async def test_repeat_respects_max_repeat():
    bot = make_bot(max_repeat=2)
    message, _ = await run(bot, "repeat 50:\n    send $i")
    assert sent(message) == ["0", "1"]

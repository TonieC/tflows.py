"""Tests for scheduled tasks: every-intervals and cron schedules."""

import asyncio

import pytest

from tests.fakes import FakeChannel, make_bot
from tflows.scheduler import CronSchedule, parse_every_header


@pytest.fixture
def bot():
    b = make_bot()
    yield b
    # Hygiene: never leak background loops between tests.
    loop = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None:
        for task in list(b.scheduler.tasks.values()):
            if task._task is not None and not task._task.done():
                task._task.cancel()


def test_parse_every_header():
    assert parse_every_header("every 1h:") == 3600
    assert parse_every_header("every 30s") == 30
    assert parse_every_header("every 5m:") == 300
    assert parse_every_header("every 1d:") == 86400
    assert parse_every_header("send hi") is None


def test_cron_invalid_expression():
    with pytest.raises(ValueError):
        CronSchedule("not a cron")
    with pytest.raises(ValueError):
        CronSchedule("* * *")


def test_cron_next_occurrence_reasonable():
    sched = CronSchedule("* * * * *")
    assert 1 <= sched.seconds_until_next() <= 61


async def test_schedule_registers_task(bot):
    channel = FakeChannel()
    task = bot.schedule("tick", "send tick", interval="60s", channel=channel)
    try:
        assert bot.scheduler.tasks["tick"] is task
        assert task.interval == 60
        assert task.code == "send tick"
    finally:
        await task.stop()


async def test_schedule_every_header_in_code(bot):
    task = bot.schedule("hourly", "every 1h:\nsend Hourly task")
    try:
        assert task.interval == 3600
        assert task.code.strip() == "send Hourly task"
    finally:
        await task.stop()


async def test_schedule_requires_timing(bot):
    with pytest.raises(ValueError):
        bot.schedule("bad", "send hi")


async def test_schedule_replaces_duplicate(bot):
    t1 = bot.schedule("dup", "send one", interval=60)
    t2 = bot.schedule("dup", "send two", interval=60)
    try:
        assert bot.scheduler.tasks["dup"] is t2
        assert len(bot.scheduler.tasks) == 1
    finally:
        await t1.stop()
        await t2.stop()


async def test_unschedule(bot):
    bot.schedule("gone", "send x", interval=60)
    assert bot.unschedule("gone") is True
    assert bot.unschedule("gone") is False


async def test_run_once_delivers_to_channel(bot):
    channel = FakeChannel()
    bot.schedule("ping", "send scheduled!", interval=60, channel=channel)
    try:
        await bot.scheduler.run_once("ping")
    finally:
        await bot.scheduler.stop_all()
    assert channel.sent == [(("scheduled!",), {})]


async def test_run_once_unknown_name(bot):
    with pytest.raises(KeyError):
        await bot.scheduler.run_once("nope")


async def test_task_loop_runs_repeatedly(bot):
    channel = FakeChannel()
    task = bot.schedule("fast", "send tick", interval=0.05, channel=channel)
    try:
        await asyncio.sleep(0.25)
        assert task.runs >= 2
        assert len(channel.sent) >= 2
    finally:
        await task.stop()
    runs_after = task.runs
    await asyncio.sleep(0.12)
    assert task.runs == runs_after  # stopped: no more executions


async def test_cron_task_registers(bot):
    task = bot.schedule("cronjob", "send hi", cron="* * * * *")
    try:
        assert task.cron is not None
    finally:
        await task.stop()


async def test_schedule_and_prefix_coexist(bot):
    from tests.fakes import FakeMessage

    channel = FakeChannel()
    bot.schedule("bg", "send background", interval=60, channel=channel)
    bot.command("hello", "send hi")
    try:
        await bot.scheduler.run_once("bg")
        message = FakeMessage(content="!hello", client=bot)
        await bot.on_message(message)
    finally:
        await bot.scheduler.stop_all()
    assert channel.sent == [(("background",), {})]
    assert message.channel.sent == [(("hi",), {})]

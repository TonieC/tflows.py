"""Script-level scheduled automation for tflows.

Python API::

    bot.schedule("hourly", code="send Hourly check-in", interval="1h",
                 channel_id=123456789)
    bot.schedule("fast", code="send hi", interval=30)  # seconds

Script-header style (the ``every`` / ``cron`` first line is informational;
the body is the scheduled script)::

    every 1h:
        send Hourly task

    cron */15 * * * *:
        send Quarter-hour task

Tasks run on :mod:`asyncio` without blocking the bot, start on demand via
:meth:`Scheduler.start`, stop cleanly with :meth:`Scheduler.stop`, and never
duplicate: re-scheduling an existing name replaces the old task.
"""

import asyncio
import logging
import re

from .utils import parse_duration

logger = logging.getLogger("tflows.scheduler")

_EVERY_RE = re.compile(r"^every\s+([^\s:]+)\s*:?\s*$", re.IGNORECASE)
_CRON_RE = re.compile(r"^cron\s+(.+?)\s*:?\s*$", re.IGNORECASE)


def parse_every_header(line: str):
    """Return interval seconds for ``every 1h:`` lines, else ``None``."""
    match = _EVERY_RE.match(line.strip())
    if not match:
        return None
    return parse_duration(match.group(1))


def parse_cron_header(line: str):
    """Return the cron expression for ``cron * * * * *:`` lines, else ``None``."""
    match = _CRON_RE.match(line.strip())
    if not match:
        return None
    return match.group(1).strip()


def strip_schedule_header(code: str) -> str:
    """Remove a leading ``every``/``cron`` header so the body runs verbatim."""
    lines = (code or "").split("\n")
    if lines and (parse_every_header(lines[0]) is not None or parse_cron_header(lines[0]) is not None):
        return "\n".join(lines[1:])
    return code or ""


def _parse_cron_field(field: str, minimum: int, maximum: int) -> set:
    values = set()
    for part in field.split(","):
        part = part.strip()
        step = 1
        if "/" in part:
            part, _, step_s = part.partition("/")
            try:
                step = max(1, int(step_s))
            except ValueError:
                raise ValueError(f"bad cron step: {field!r}") from None
        if part in ("*", ""):
            lo, hi = minimum, maximum
        elif "-" in part:
            lo_s, _, hi_s = part.partition("-")
            lo, hi = int(lo_s), int(hi_s)
        else:
            lo = hi = int(part)
        if lo < minimum or hi > maximum or lo > hi:
            raise ValueError(f"cron value out of range: {field!r}")
        values.update(range(lo, hi + 1, step))
    return values


class CronSchedule:
    """Minimal 5-field cron (minute hour day month weekday)."""

    def __init__(self, expression: str):
        fields = expression.split()
        if len(fields) != 5:
            raise ValueError(
                f"cron needs 5 fields (minute hour day month weekday), got: {expression!r}"
            )
        self.minutes = _parse_cron_field(fields[0], 0, 59)
        self.hours = _parse_cron_field(fields[1], 0, 23)
        self.days = _parse_cron_field(fields[2], 1, 31)
        self.months = _parse_cron_field(fields[3], 1, 12)
        self.weekdays = _parse_cron_field(fields[4], 0, 6)

    def seconds_until_next(self, now=None) -> float:
        import datetime as _dt

        now = now or _dt.datetime.now(_dt.timezone.utc).replace(second=0, microsecond=0)
        probe = now + _dt.timedelta(minutes=1)
        for _ in range(525600 * 2):  # ~2 years of minutes, then give up
            # cron weekday: 0=Sunday..6=Saturday; python: Monday=0..Sunday=6
            cron_dow = (probe.weekday() + 1) % 7
            if (
                probe.minute in self.minutes
                and probe.hour in self.hours
                and probe.day in self.days
                and probe.month in self.months
                and cron_dow in self.weekdays
            ):
                return max(1.0, (probe - now).total_seconds())
            probe += _dt.timedelta(minutes=1)
        return 3600.0


class ScheduledTask:
    """One named recurring script."""

    def __init__(self, name, code, bot=None, interval=None, cron=None, channel=None):
        self.name = name
        self.code = strip_schedule_header(code)
        self.bot = bot
        self.interval = interval
        self.cron = CronSchedule(cron) if isinstance(cron, str) else cron
        self.channel = channel
        self._task = None
        self.runs = 0

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.running:
            return
        self._task = asyncio.ensure_future(self._loop())

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _wait(self) -> None:
        if self.cron is not None:
            await asyncio.sleep(self.cron.seconds_until_next())
        else:
            await asyncio.sleep(self.interval)

    async def _loop(self) -> None:
        try:
            while True:
                await self._wait()
                await self.run_once()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("[tflow] scheduled task %r crashed", self.name)

    async def run_once(self) -> None:
        from .context import FlowContext

        bot = self.bot
        if bot is None:
            return
        try:
            ctx = FlowContext.for_scheduler(bot, self.channel, command_name=self.name)
            await bot.engine.run(ctx, self.code)
            self.runs += 1
        except Exception:
            logger.exception("[tflow] scheduled task %r failed", self.name)


class Scheduler:
    """Owns a bot's scheduled tasks. Created per-:class:`FlowBot`."""

    def __init__(self, bot):
        self.bot = bot
        self.tasks: dict = {}

    def schedule(self, name, code, interval=None, cron=None, channel=None) -> ScheduledTask:
        """Register (or replace) a task. At least one of interval/cron required.

        ``interval`` accepts seconds or duration strings (``"30s"``,
        ``"5m"``, ``"1h"``, ``"1d"``). A leading ``every``/``cron`` header in
        ``code`` supplies the schedule when neither is passed explicitly.
        """
        if interval is None and cron is None:
            for line in (code or "").split("\n"):
                line = line.strip()
                if not line:
                    continue
                interval = parse_every_header(line)
                if interval is None:
                    cron = parse_cron_header(line)
                break
        if isinstance(interval, str):
            interval = parse_duration(interval)
        if interval is not None and interval <= 0:
            raise ValueError(f"interval must be positive, got {interval!r}")
        if interval is None and cron is None:
            raise ValueError("schedule needs an interval (e.g. '1h') or a cron expression")
        old = self.tasks.get(name)
        if old is not None and old.running:
            # Replaced below; stop the previous loop to avoid duplicates.
            old._task.cancel()
        task = ScheduledTask(name, code, bot=self.bot, interval=interval, cron=cron, channel=channel)
        self.tasks[name] = task
        return task

    def unschedule(self, name) -> bool:
        task = self.tasks.pop(name, None)
        if task is None:
            return False
        if task.running:
            task._task.cancel()
        return True

    def start_all(self) -> None:
        for task in self.tasks.values():
            task.start()

    async def stop_all(self) -> None:
        for task in list(self.tasks.values()):
            await task.stop()

    async def run_once(self, name: str) -> None:
        task = self.tasks.get(name)
        if task is None:
            raise KeyError(f"no scheduled task named {name!r}")
        await task.run_once()

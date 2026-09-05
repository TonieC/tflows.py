"""SQLite-backed persistent per-server state for tflows scripts.

Scripts use the ``set`` / ``get`` / ``del`` / ``incr`` functions (registered
in :mod:`tflows.function.state_funcs`)::

    set points 10
    set points +5
    get points
    incr points
    del points

Keys are automatically namespaced by guild/server id so state is isolated
per server (``"global"`` is used outside a guild). Values are stored as
text; integers, floats and booleans round-trip through best-effort parsing.

Thread/loop safety: a single connection guarded by a lock, with all blocking
sqlite calls executed in a worker thread via :func:`asyncio.to_thread` so
Discord's event loop is never blocked.
"""

import asyncio
import logging
import sqlite3
import threading

logger = logging.getLogger("tflows.state")


def guild_namespace(ctx) -> str:
    """Return the storage namespace for a context (guild id or ``"global"``)."""
    try:
        guild = ctx.guild
    except Exception:
        guild = None
    if guild is None:
        return "global"
    return str(getattr(guild, "id", "global"))


def format_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def parse_value(raw: str):
    """Best-effort round-trip: int -> float -> bool -> str."""
    if raw is None:
        return ""
    lowered = raw.strip().lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
        return False
    try:
        return int(raw)
    except (TypeError, ValueError):
        pass
    try:
        return float(raw)
    except (TypeError, ValueError):
        pass
    return raw


class StateStore:
    """Async-safe SQLite key/value store namespaced by guild.

    Parameters
    ----------
    path:
        Filesystem path of the sqlite database. ``":memory:"`` keeps state
        in memory (useful for tests; data lives as long as the store does).
    """

    def __init__(self, path: str = "tflows.db"):
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS state "
                "(guild TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, "
                "PRIMARY KEY (guild, key))"
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Sync internals (run in a worker thread)
    # ------------------------------------------------------------------
    def _get_sync(self, guild: str, key: str):
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM state WHERE guild = ? AND key = ?", (guild, key)
            ).fetchone()
        return row[0] if row else None

    def _set_sync(self, guild: str, key: str, value: str):
        with self._lock:
            self._conn.execute(
                "INSERT INTO state (guild, key, value) VALUES (?, ?, ?) "
                "ON CONFLICT (guild, key) DO UPDATE SET value = excluded.value",
                (guild, key, value),
            )
            self._conn.commit()

    def _del_sync(self, guild: str, key: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM state WHERE guild = ? AND key = ?", (guild, key)
            )
            self._conn.commit()
            return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Async API
    # ------------------------------------------------------------------
    async def get(self, guild: str, key: str, default=None):
        try:
            value = await asyncio.to_thread(self._get_sync, guild, key)
        except Exception:
            logger.exception("[tflow] state get failed for %r", key)
            return default
        return value if value is not None else default

    async def set(self, guild: str, key: str, value) -> None:
        try:
            await asyncio.to_thread(self._set_sync, guild, key, format_value(value))
        except Exception:
            logger.exception("[tflow] state set failed for %r", key)

    async def delete(self, guild: str, key: str) -> bool:
        try:
            return await asyncio.to_thread(self._del_sync, guild, key)
        except Exception:
            logger.exception("[tflow] state delete failed for %r", key)
            return False

    async def incr(self, guild: str, key: str, delta: int = 1):
        """Atomically increment ``key`` by ``delta``; returns the new value."""
        def _op():
            with self._lock:
                row = self._conn.execute(
                    "SELECT value FROM state WHERE guild = ? AND key = ?", (guild, key)
                ).fetchone()
                try:
                    current = int(row[0]) if row else 0
                except (TypeError, ValueError):
                    try:
                        current = float(row[0]) if row else 0
                    except (TypeError, ValueError):
                        current = 0
                new_value = current + delta
                if isinstance(new_value, float) and new_value.is_integer():
                    new_value = int(new_value)
                self._conn.execute(
                    "INSERT INTO state (guild, key, value) VALUES (?, ?, ?) "
                    "ON CONFLICT (guild, key) DO UPDATE SET value = excluded.value",
                    (guild, key, str(new_value)),
                )
                self._conn.commit()
                return new_value

        try:
            return await asyncio.to_thread(_op)
        except Exception:
            logger.exception("[tflow] state incr failed for %r", key)
            return delta

    def close(self) -> None:
        try:
            with self._lock:
                self._conn.close()
        except Exception:
            pass

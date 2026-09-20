"""SQLite-backed state: which uids have been seen, and last metric values per uid.

This is what turns snapshot fetches into deltas — the whole point of argus.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sqlite3


class StateStore:
    def __init__(self, path: str | pathlib.Path):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS seen (
                uid TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                first_seen TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS seen_source ON seen (source);
            CREATE TABLE IF NOT EXISTS metrics (
                uid TEXT NOT NULL,
                key TEXT NOT NULL,
                value REAL NOT NULL,
                updated TEXT NOT NULL,
                PRIMARY KEY (uid, key)
            );
            CREATE TABLE IF NOT EXISTS sources (
                source TEXT PRIMARY KEY,
                seeded_at TEXT NOT NULL
            );
            """
        )
        self.db.commit()

    @staticmethod
    def _now() -> str:
        return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    def is_seeded(self, source: str) -> bool:
        row = self.db.execute("SELECT 1 FROM sources WHERE source = ?", (source,)).fetchone()
        return row is not None

    def mark_seeded(self, source: str) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO sources (source, seeded_at) VALUES (?, ?)",
            (source, self._now()),
        )
        self.db.commit()

    def known_uids(self, source: str) -> set[str]:
        rows = self.db.execute("SELECT uid FROM seen WHERE source = ?", (source,))
        return {r[0] for r in rows}

    def add_seen(self, records) -> None:
        now = self._now()
        self.db.executemany(
            "INSERT OR IGNORE INTO seen (uid, source, first_seen) VALUES (?, ?, ?)",
            [(r.uid, r.source, now) for r in records],
        )
        self.db.commit()

    def get_metric(self, uid: str, key: str) -> float | None:
        row = self.db.execute(
            "SELECT value FROM metrics WHERE uid = ? AND key = ?", (uid, key)
        ).fetchone()
        return row[0] if row else None

    def set_metric(self, uid: str, key: str, value: float) -> None:
        self.db.execute(
            "INSERT INTO metrics (uid, key, value, updated) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(uid, key) DO UPDATE SET value = excluded.value, updated = excluded.updated",
            (uid, key, value, self._now()),
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

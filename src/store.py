"""SQLite persistence for queue, attempts, call records, and dashboard stats."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from src import config


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Store:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or config.DATABASE_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS call_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contact_id TEXT NOT NULL,
                    trigger_id TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    first_name TEXT,
                    last_name TEXT,
                    email TEXT,
                    timezone TEXT,
                    tags_json TEXT,
                    brief TEXT,
                    campaign_id TEXT NOT NULL DEFAULT 'general',
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS call_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contact_id TEXT NOT NULL,
                    queue_id INTEGER,
                    vapi_call_id TEXT,
                    outcome TEXT,
                    cost REAL,
                    duration_seconds INTEGER,
                    recording_url TEXT,
                    transcript TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS active_calls (
                    vapi_call_id TEXT PRIMARY KEY,
                    contact_id TEXT NOT NULL,
                    queue_id INTEGER,
                    started_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contact_id TEXT NOT NULL,
                    vapi_call_id TEXT,
                    slot_start TEXT NOT NULL,
                    slot_end TEXT NOT NULL,
                    gcal_event_id TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_queue_pending
                ON call_queue(contact_id, trigger_id)
                WHERE status = 'pending';
                """
            )
            self._migrate_queue_campaign_id(conn)

    def _migrate_queue_campaign_id(self, conn: sqlite3.Connection) -> None:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(call_queue)")}
        if "campaign_id" not in columns:
            conn.execute(
                "ALTER TABLE call_queue ADD COLUMN campaign_id TEXT NOT NULL DEFAULT 'general'"
            )

    def enqueue(
        self,
        *,
        contact_id: str,
        trigger_id: str,
        phone: str,
        first_name: str = "",
        last_name: str = "",
        email: str = "",
        timezone: str = "",
        tags: list[str] | None = None,
        brief: str = "",
        campaign_id: str = "general",
    ) -> int | None:
        now = _utcnow()
        tags_json = json.dumps(tags or [])
        with self._conn() as conn:
            try:
                cur = conn.execute(
                    """
                    INSERT INTO call_queue
                    (contact_id, trigger_id, phone, first_name, last_name, email,
                     timezone, tags_json, brief, campaign_id, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (
                        contact_id,
                        trigger_id,
                        phone,
                        first_name,
                        last_name,
                        email,
                        timezone,
                        tags_json,
                        brief,
                        campaign_id,
                        now,
                        now,
                    ),
                )
                return int(cur.lastrowid)
            except sqlite3.IntegrityError:
                return None

    def get_pending_queue(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM call_queue
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_queue_status(self, queue_id: int, status: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE call_queue SET status = ?, updated_at = ? WHERE id = ?",
                (status, _utcnow(), queue_id),
            )

    def count_active_calls(self) -> int:
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM active_calls").fetchone()
        return int(row["c"])

    def register_active_call(
        self, vapi_call_id: str, contact_id: str, queue_id: int | None
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO active_calls (vapi_call_id, contact_id, queue_id, started_at)
                VALUES (?, ?, ?, ?)
                """,
                (vapi_call_id, contact_id, queue_id, _utcnow()),
            )

    def clear_active_call(self, vapi_call_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM active_calls WHERE vapi_call_id = ?", (vapi_call_id,))

    def record_attempt(
        self,
        *,
        contact_id: str,
        queue_id: int | None = None,
        vapi_call_id: str | None = None,
        outcome: str | None = None,
        cost: float | None = None,
        duration_seconds: int | None = None,
        recording_url: str | None = None,
        transcript: str | None = None,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO call_attempts
                (contact_id, queue_id, vapi_call_id, outcome, cost, duration_seconds,
                 recording_url, transcript, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    contact_id,
                    queue_id,
                    vapi_call_id,
                    outcome,
                    cost,
                    duration_seconds,
                    recording_url,
                    transcript,
                    _utcnow(),
                ),
            )
            return int(cur.lastrowid)

    def update_attempt_recording(
        self, vapi_call_id: str, recording_url: str, transcript: str | None = None
    ) -> None:
        with self._conn() as conn:
            if transcript:
                conn.execute(
                    """
                    UPDATE call_attempts
                    SET recording_url = ?, transcript = COALESCE(?, transcript)
                    WHERE vapi_call_id = ?
                    """,
                    (recording_url, transcript, vapi_call_id),
                )
            else:
                conn.execute(
                    "UPDATE call_attempts SET recording_url = ? WHERE vapi_call_id = ?",
                    (recording_url, vapi_call_id),
                )

    def get_attempt_count(self, contact_id: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM call_attempts WHERE contact_id = ?",
                (contact_id,),
            ).fetchone()
        return int(row["c"])

    def get_last_attempt_time(self, contact_id: str) -> datetime | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT created_at FROM call_attempts
                WHERE contact_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (contact_id,),
            ).fetchone()
        if not row:
            return None
        return datetime.fromisoformat(row["created_at"])

    def record_booking(
        self,
        *,
        contact_id: str,
        vapi_call_id: str | None,
        slot_start: str,
        slot_end: str,
        gcal_event_id: str | None = None,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO bookings
                (contact_id, vapi_call_id, slot_start, slot_end, gcal_event_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (contact_id, vapi_call_id, slot_start, slot_end, gcal_event_id, _utcnow()),
            )
            return int(cur.lastrowid)

    def get_dashboard_stats(self) -> dict[str, Any]:
        with self._conn() as conn:
            pending = conn.execute(
                "SELECT COUNT(*) AS c FROM call_queue WHERE status = 'pending'"
            ).fetchone()["c"]
            active = conn.execute("SELECT COUNT(*) AS c FROM active_calls").fetchone()["c"]
            today = datetime.now(timezone.utc).date().isoformat()
            calls_today = conn.execute(
                "SELECT COUNT(*) AS c FROM call_attempts WHERE created_at LIKE ?",
                (f"{today}%",),
            ).fetchone()["c"]
            booked_today = conn.execute(
                "SELECT COUNT(*) AS c FROM bookings WHERE created_at LIKE ?",
                (f"{today}%",),
            ).fetchone()["c"]
            needs_human = conn.execute(
                """
                SELECT COUNT(*) AS c FROM call_attempts
                WHERE outcome = 'needs_human' AND created_at LIKE ?
                """,
                (f"{today}%",),
            ).fetchone()["c"]
            spend_row = conn.execute(
                """
                SELECT COALESCE(SUM(cost), 0) AS total FROM call_attempts
                WHERE created_at LIKE ?
                """,
                (f"{today}%",),
            ).fetchone()
            recent = conn.execute(
                """
                SELECT contact_id, outcome, cost, duration_seconds, created_at,
                       recording_url, vapi_call_id
                FROM call_attempts ORDER BY created_at DESC LIMIT 20
                """
            ).fetchall()
        return {
            "pending_queue": pending,
            "active_calls": active,
            "calls_today": calls_today,
            "booked_today": booked_today,
            "needs_human_today": needs_human,
            "spend_today": round(float(spend_row["total"] or 0), 2),
            "recent_attempts": [dict(r) for r in recent],
        }

    def get_daily_summary_stats(self, day: str | None = None) -> dict[str, Any]:
        day = day or datetime.now(timezone.utc).date().isoformat()
        prefix = f"{day}%"
        with self._conn() as conn:
            total_calls = conn.execute(
                "SELECT COUNT(*) AS c FROM call_attempts WHERE created_at LIKE ?",
                (prefix,),
            ).fetchone()["c"]
            booked = conn.execute(
                "SELECT COUNT(*) AS c FROM bookings WHERE created_at LIKE ?",
                (prefix,),
            ).fetchone()["c"]
            needs_human = conn.execute(
                """
                SELECT COUNT(*) AS c FROM call_attempts
                WHERE outcome = 'needs_human' AND created_at LIKE ?
                """,
                (prefix,),
            ).fetchone()["c"]
            spend = conn.execute(
                "SELECT COALESCE(SUM(cost), 0) AS total FROM call_attempts WHERE created_at LIKE ?",
                (prefix,),
            ).fetchone()["total"]
            by_outcome = conn.execute(
                """
                SELECT outcome, COUNT(*) AS c FROM call_attempts
                WHERE created_at LIKE ?
                GROUP BY outcome
                """,
                (prefix,),
            ).fetchall()
        return {
            "day": day,
            "total_calls": total_calls,
            "booked": booked,
            "needs_human": needs_human,
            "spend": round(float(spend or 0), 2),
            "by_outcome": {r["outcome"] or "unknown": r["c"] for r in by_outcome},
        }

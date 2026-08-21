"""
database_manager.py - SQLite persistence layer for NeuroShield Eye.

All analytics data (screen sessions, breaks, posture events) are stored
in a local SQLite database at %APPDATA%/NeuroShieldEye/data.db.

Thread-safety: Each call opens and closes its own connection so this
module is safe to call from any thread without locking overhead.
"""

import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from utils.logger import get_logger

log = get_logger("database_manager")


def _get_db_path() -> Path:
    app_data = os.environ.get("APPDATA", Path.home())
    db_dir = Path(app_data) / "NeuroShieldEye"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "data.db"


class DatabaseManager:
    """
    Handles all SQLite operations for NeuroShield Eye.

    Tables:
      - daily_stats  : One row per calendar day summarizing usage
      - break_events : Individual break records (start, end, completed flag)
      - posture_events: Posture reminder dismissal timestamps
    """

    def __init__(self) -> None:
        self._db_path = _get_db_path()
        self._init_schema()
        log.info("Database initialized at %s", self._db_path)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_schema(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS daily_stats (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            stat_date       TEXT UNIQUE NOT NULL,   -- ISO date YYYY-MM-DD
            screen_minutes  INTEGER NOT NULL DEFAULT 0,
            breaks_done     INTEGER NOT NULL DEFAULT 0,
            breaks_missed   INTEGER NOT NULL DEFAULT 0,
            posture_alerts  INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS break_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time  TEXT NOT NULL,   -- ISO datetime
            end_time    TEXT,            -- NULL if missed/skipped
            completed   INTEGER NOT NULL DEFAULT 0,   -- 1=completed, 0=skipped
            break_type  TEXT NOT NULL DEFAULT '20-20-20'
        );

        CREATE TABLE IF NOT EXISTS posture_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time      TEXT NOT NULL,
            acknowledged    INTEGER NOT NULL DEFAULT 1
        );
        """
        try:
            with self._connect() as conn:
                conn.executescript(ddl)
        except sqlite3.Error as e:
            log.error("Schema init failed: %s", e)

    # ------------------------------------------------------------------
    # Screen time
    # ------------------------------------------------------------------

    def add_screen_minutes(self, minutes: int, day: Optional[date] = None) -> None:
        """Increment screen_minutes for a given day (default: today)."""
        day_str = (day or date.today()).isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO daily_stats (stat_date, screen_minutes)
                    VALUES (?, ?)
                    ON CONFLICT(stat_date) DO UPDATE SET
                        screen_minutes = screen_minutes + excluded.screen_minutes
                    """,
                    (day_str, minutes),
                )
        except sqlite3.Error as e:
            log.error("add_screen_minutes error: %s", e)

    # ------------------------------------------------------------------
    # Break tracking
    # ------------------------------------------------------------------

    def record_break_start(self, break_type: str = "20-20-20") -> int:
        """Insert a break_event row and return its ID."""
        now = datetime.now().isoformat()
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "INSERT INTO break_events (start_time, break_type) VALUES (?, ?)",
                    (now, break_type),
                )
                return cursor.lastrowid or 0
        except sqlite3.Error as e:
            log.error("record_break_start error: %s", e)
            return 0

    def record_break_end(self, break_id: int, completed: bool) -> None:
        """Update the break_event with end time and completion status."""
        now = datetime.now().isoformat()
        day_str = date.today().isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE break_events SET end_time=?, completed=? WHERE id=?",
                    (now, int(completed), break_id),
                )
                if completed:
                    conn.execute(
                        """
                        INSERT INTO daily_stats (stat_date, breaks_done)
                        VALUES (?, 1)
                        ON CONFLICT(stat_date) DO UPDATE SET
                            breaks_done = breaks_done + 1
                        """,
                        (day_str,),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO daily_stats (stat_date, breaks_missed)
                        VALUES (?, 1)
                        ON CONFLICT(stat_date) DO UPDATE SET
                            breaks_missed = breaks_missed + 1
                        """,
                        (day_str,),
                    )
        except sqlite3.Error as e:
            log.error("record_break_end error: %s", e)

    # ------------------------------------------------------------------
    # Posture events
    # ------------------------------------------------------------------

    def record_posture_alert(self) -> None:
        """Log a posture reminder shown to the user."""
        now = datetime.now().isoformat()
        day_str = date.today().isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO posture_events (event_time) VALUES (?)", (now,)
                )
                conn.execute(
                    """
                    INSERT INTO daily_stats (stat_date, posture_alerts)
                    VALUES (?, 1)
                    ON CONFLICT(stat_date) DO UPDATE SET
                        posture_alerts = posture_alerts + 1
                    """,
                    (day_str,),
                )
        except sqlite3.Error as e:
            log.error("record_posture_alert error: %s", e)

    # ------------------------------------------------------------------
    # Analytics queries
    # ------------------------------------------------------------------

    def get_today_stats(self) -> dict:
        """Return today's aggregated stats as a dictionary."""
        day_str = date.today().isoformat()
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM daily_stats WHERE stat_date = ?", (day_str,)
                ).fetchone()
                if row:
                    return dict(row)
        except sqlite3.Error as e:
            log.error("get_today_stats error: %s", e)
        return {
            "stat_date": day_str,
            "screen_minutes": 0,
            "breaks_done": 0,
            "breaks_missed": 0,
            "posture_alerts": 0,
        }

    def get_weekly_stats(self) -> list[dict]:
        """Return last 7 days of daily_stats, oldest first."""
        today = date.today()
        start = (today - timedelta(days=6)).isoformat()
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM daily_stats WHERE stat_date >= ? ORDER BY stat_date ASC",
                    (start,),
                ).fetchall()
                return [dict(r) for r in rows]
        except sqlite3.Error as e:
            log.error("get_weekly_stats error: %s", e)
            return []

    def get_break_streak(self) -> int:
        """
        Return the current streak of consecutive days with at least one completed break.
        """
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT stat_date, breaks_done
                    FROM daily_stats
                    ORDER BY stat_date DESC
                    LIMIT 30
                    """
                ).fetchall()

            streak = 0
            today = date.today()
            for row in rows:
                day = date.fromisoformat(row["stat_date"])
                expected = today - timedelta(days=streak)
                if day == expected and row["breaks_done"] > 0:
                    streak += 1
                else:
                    break
            return streak
        except sqlite3.Error as e:
            log.error("get_break_streak error: %s", e)
            return 0

    def get_all_time_total_hours(self) -> float:
        """Return total tracked screen time across all days in hours."""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT SUM(screen_minutes) as total FROM daily_stats"
                ).fetchone()
                total = row["total"] if row and row["total"] else 0
                return round(total / 60, 1)
        except sqlite3.Error as e:
            log.error("get_all_time_total_hours error: %s", e)
            return 0.0

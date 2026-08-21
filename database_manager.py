"""
database_manager.py - SQLite persistence for NeuroShield-Eye Pro.

Stores local auth, protection profiles, and analytics in a single
offline file: %APPDATA%/NeuroShieldEye/neuroshield.db (or ~/.NeuroShieldEye
on non-Windows). Each public method opens its own connection so calls
are safe from any thread.

On first launch the database is seeded with:
  - Four ADHD-friendly protection profiles
  - Seven days of realistic screen-time / eye-strain logs
"""

from __future__ import annotations

import hashlib
import hmac
import os
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from logger import get_logger

log = get_logger("database_manager")

_PBKDF2_ROUNDS = 120_000
_DB_FILENAME = "neuroshield.db"
_OLD_DB_FILENAME = "data.db"

_BUILTIN_PROFILES = [
    {
        "name": "Late Night Coding",
        "description": "Warm amber tint, gentle dim. Built for long evening sessions.",
        "blue_light_enabled": 1,
        "color_temperature": 2200,
        "blue_light_opacity": 0.45,
        "dim_enabled": 1,
        "dim_opacity": 0.18,
        "focus_enabled": 0,
        "is_preset": 1,
    },
    {
        "name": "Reading",
        "description": "Softer contrast and a mild filter so text stays comfortable.",
        "blue_light_enabled": 1,
        "color_temperature": 4000,
        "blue_light_opacity": 0.22,
        "dim_enabled": 1,
        "dim_opacity": 0.08,
        "focus_enabled": 0,
        "is_preset": 1,
    },
    {
        "name": "Outdoor",
        "description": "Near-daylight temperature. Minimal overlay for bright rooms.",
        "blue_light_enabled": 1,
        "color_temperature": 6200,
        "blue_light_opacity": 0.06,
        "dim_enabled": 0,
        "dim_opacity": 0.0,
        "focus_enabled": 0,
        "is_preset": 1,
    },
    {
        "name": "Gaming Mode",
        "description": "Blue-light off, brightness high. Keep colors punchy.",
        "blue_light_enabled": 0,
        "color_temperature": 6500,
        "blue_light_opacity": 0.0,
        "dim_enabled": 0,
        "dim_opacity": 0.0,
        "focus_enabled": 0,
        "is_preset": 1,
    },
    {
        "name": "Deep Focus",
        "description": "Visual anchor on. Dim the noise, keep the active window bright.",
        "blue_light_enabled": 1,
        "color_temperature": 3000,
        "blue_light_opacity": 0.30,
        "dim_enabled": 0,
        "dim_opacity": 0.0,
        "focus_enabled": 1,
        "is_preset": 1,
    },
]


def _get_db_dir() -> Path:
    app_data = os.environ.get("APPDATA")
    if app_data:
        db_dir = Path(app_data) / "NeuroShieldEye"
    else:
        db_dir = Path.home() / ".NeuroShieldEye"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir


def _get_db_path() -> Path:
    db_dir = _get_db_dir()
    new_path = db_dir / _DB_FILENAME
    old_path = db_dir / _OLD_DB_FILENAME
    if old_path.exists() and not new_path.exists():
        try:
            old_path.rename(new_path)
            log.info("Migrated database %s → %s", old_path, new_path)
        except OSError as e:
            log.warning("Could not migrate old database: %s", e)
            return old_path
    return new_path


def _hash_pin(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        salt.encode("utf-8"),
        _PBKDF2_ROUNDS,
    ).hex()


class DatabaseManager:
    """
    SQLite facade for NeuroShield-Eye Pro.

    Tables:
      users            – local profile + salted PIN hash
      profiles         – named protection presets (CRUD)
      daily_stats      – per-day screen time, breaks, eye strain
      break_events     – individual 20-20-20 / custom breaks
      posture_events   – posture reminder log
      app_meta         – key/value (seed flag, active profile)
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = Path(db_path) if db_path else _get_db_path()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._seed_if_needed()
        log.info("Database initialized at %s", self._db_path)

    # ------------------------------------------------------------------
    # Connection / schema
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_schema(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name  TEXT NOT NULL,
            pin_salt      TEXT NOT NULL,
            pin_hash      TEXT NOT NULL,
            created_at    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS profiles (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            name                 TEXT NOT NULL,
            description          TEXT NOT NULL DEFAULT '',
            blue_light_enabled   INTEGER NOT NULL DEFAULT 1,
            color_temperature    INTEGER NOT NULL DEFAULT 3400,
            blue_light_opacity   REAL    NOT NULL DEFAULT 0.35,
            dim_enabled          INTEGER NOT NULL DEFAULT 0,
            dim_opacity          REAL    NOT NULL DEFAULT 0.0,
            focus_enabled        INTEGER NOT NULL DEFAULT 0,
            is_preset            INTEGER NOT NULL DEFAULT 0,
            created_at           TEXT NOT NULL,
            updated_at           TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS daily_stats (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            stat_date         TEXT UNIQUE NOT NULL,
            screen_minutes    INTEGER NOT NULL DEFAULT 0,
            breaks_done       INTEGER NOT NULL DEFAULT 0,
            breaks_missed     INTEGER NOT NULL DEFAULT 0,
            posture_alerts    INTEGER NOT NULL DEFAULT 0,
            eye_strain_score  INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS break_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time  TEXT NOT NULL,
            end_time    TEXT,
            completed   INTEGER NOT NULL DEFAULT 0,
            break_type  TEXT NOT NULL DEFAULT '20-20-20'
        );

        CREATE TABLE IF NOT EXISTS posture_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time      TEXT NOT NULL,
            acknowledged    INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS app_meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        """
        try:
            with self._connect() as conn:
                conn.executescript(ddl)
                self._migrate(conn)
        except sqlite3.Error as e:
            log.error("Schema init failed: %s", e)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(daily_stats)")}
        if "eye_strain_score" not in cols:
            conn.execute(
                "ALTER TABLE daily_stats "
                "ADD COLUMN eye_strain_score INTEGER NOT NULL DEFAULT 0"
            )

    def _meta_get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT value FROM app_meta WHERE key = ?", (key,)
                ).fetchone()
                return row["value"] if row else default
        except sqlite3.Error as e:
            log.error("meta_get error: %s", e)
            return default

    def _meta_set(self, key: str, value: str) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO app_meta (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, value),
                )
        except sqlite3.Error as e:
            log.error("meta_set error: %s", e)

    # ------------------------------------------------------------------
    # First-run seed
    # ------------------------------------------------------------------

    def _seed_if_needed(self) -> None:
        if self._meta_get("seeded") == "1":
            return
        try:
            with self._connect() as conn:
                profile_count = conn.execute("SELECT COUNT(*) AS n FROM profiles").fetchone()["n"]
                if profile_count == 0:
                    now = datetime.now().isoformat()
                    for p in _BUILTIN_PROFILES:
                        conn.execute(
                            """
                            INSERT INTO profiles (
                                name, description, blue_light_enabled, color_temperature,
                                blue_light_opacity, dim_enabled, dim_opacity, focus_enabled,
                                is_preset, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                p["name"], p["description"], p["blue_light_enabled"],
                                p["color_temperature"], p["blue_light_opacity"],
                                p["dim_enabled"], p["dim_opacity"], p["focus_enabled"],
                                p["is_preset"], now, now,
                            ),
                        )

                stats_count = conn.execute("SELECT COUNT(*) AS n FROM daily_stats").fetchone()["n"]
                if stats_count == 0:
                    self._seed_week(conn)

                first = conn.execute("SELECT id FROM profiles ORDER BY id ASC LIMIT 1").fetchone()
                if first:
                    conn.execute(
                        """
                        INSERT INTO app_meta (key, value) VALUES ('active_profile_id', ?)
                        ON CONFLICT(key) DO UPDATE SET value = excluded.value
                        """,
                        (str(first["id"]),),
                    )

                conn.execute(
                    """
                    INSERT INTO app_meta (key, value) VALUES ('seeded', '1')
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """
                )
            log.info("First-run demo data seeded.")
        except sqlite3.Error as e:
            log.error("Seed failed: %s", e)

    def _seed_week(self, conn: sqlite3.Connection) -> None:
        rng = random.Random(20260821)
        today = date.today()
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            if day.weekday() >= 5:
                minutes = rng.randint(95, 250)
            else:
                minutes = rng.randint(310, 545)
            breaks_done = max(0, minutes // 28 + rng.randint(-1, 2))
            breaks_missed = rng.randint(0, 3)
            posture = rng.randint(1, 6)
            strain = max(8, min(96, int(minutes / 6.2) + rng.randint(-8, 12)))
            conn.execute(
                """
                INSERT INTO daily_stats (
                    stat_date, screen_minutes, breaks_done, breaks_missed,
                    posture_alerts, eye_strain_score
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(stat_date) DO NOTHING
                """,
                (day.isoformat(), minutes, breaks_done, breaks_missed, posture, strain),
            )

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def has_user(self) -> bool:
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
                return bool(row and row["n"] > 0)
        except sqlite3.Error as e:
            log.error("has_user error: %s", e)
            return False

    def get_user(self) -> Optional[dict]:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT id, display_name, created_at FROM users ORDER BY id ASC LIMIT 1"
                ).fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            log.error("get_user error: %s", e)
            return None

    def create_user(self, display_name: str, pin: str) -> bool:
        name = (display_name or "").strip()
        if not name or not self._valid_pin(pin):
            return False
        if self.has_user():
            return False
        salt = os.urandom(16).hex()
        pin_hash = _hash_pin(pin, salt)
        now = datetime.now().isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO users (display_name, pin_salt, pin_hash, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (name, salt, pin_hash, now),
                )
            log.info("Local profile created for '%s'.", name)
            return True
        except sqlite3.Error as e:
            log.error("create_user error: %s", e)
            return False

    def verify_pin(self, pin: str) -> bool:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT pin_salt, pin_hash FROM users ORDER BY id ASC LIMIT 1"
                ).fetchone()
            if not row:
                return False
            candidate = _hash_pin(pin, row["pin_salt"])
            return hmac.compare_digest(candidate, row["pin_hash"])
        except sqlite3.Error as e:
            log.error("verify_pin error: %s", e)
            return False

    def change_pin(self, current_pin: str, new_pin: str) -> bool:
        if not self.verify_pin(current_pin) or not self._valid_pin(new_pin):
            return False
        salt = os.urandom(16).hex()
        pin_hash = _hash_pin(new_pin, salt)
        try:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE users SET pin_salt = ?, pin_hash = ? WHERE id = ("
                    "SELECT id FROM users ORDER BY id ASC LIMIT 1)",
                    (salt, pin_hash),
                )
            log.info("PIN updated.")
            return True
        except sqlite3.Error as e:
            log.error("change_pin error: %s", e)
            return False

    def update_display_name(self, display_name: str) -> bool:
        name = (display_name or "").strip()
        if not name:
            return False
        try:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE users SET display_name = ? WHERE id = ("
                    "SELECT id FROM users ORDER BY id ASC LIMIT 1)",
                    (name,),
                )
            return True
        except sqlite3.Error as e:
            log.error("update_display_name error: %s", e)
            return False

    @staticmethod
    def _valid_pin(pin: str) -> bool:
        return pin.isdigit() and 4 <= len(pin) <= 6

    # ------------------------------------------------------------------
    # Protection profiles (CRUD)
    # ------------------------------------------------------------------

    def list_profiles(self) -> list[dict]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM profiles ORDER BY is_preset DESC, name COLLATE NOCASE ASC"
                ).fetchall()
                return [dict(r) for r in rows]
        except sqlite3.Error as e:
            log.error("list_profiles error: %s", e)
            return []

    def get_profile(self, profile_id: int) -> Optional[dict]:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM profiles WHERE id = ?", (profile_id,)
                ).fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            log.error("get_profile error: %s", e)
            return None

    def create_profile(self, data: dict) -> Optional[int]:
        now = datetime.now().isoformat()
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO profiles (
                        name, description, blue_light_enabled, color_temperature,
                        blue_light_opacity, dim_enabled, dim_opacity, focus_enabled,
                        is_preset, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                    """,
                    (
                        data.get("name", "Untitled").strip() or "Untitled",
                        data.get("description", ""),
                        int(bool(data.get("blue_light_enabled", True))),
                        int(data.get("color_temperature", 3400)),
                        float(data.get("blue_light_opacity", 0.35)),
                        int(bool(data.get("dim_enabled", False))),
                        float(data.get("dim_opacity", 0.0)),
                        int(bool(data.get("focus_enabled", False))),
                        now, now,
                    ),
                )
                return cursor.lastrowid
        except sqlite3.Error as e:
            log.error("create_profile error: %s", e)
            return None

    def update_profile(self, profile_id: int, data: dict) -> bool:
        now = datetime.now().isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE profiles SET
                        name = ?, description = ?,
                        blue_light_enabled = ?, color_temperature = ?,
                        blue_light_opacity = ?, dim_enabled = ?,
                        dim_opacity = ?, focus_enabled = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        data.get("name", "Untitled").strip() or "Untitled",
                        data.get("description", ""),
                        int(bool(data.get("blue_light_enabled", True))),
                        int(data.get("color_temperature", 3400)),
                        float(data.get("blue_light_opacity", 0.35)),
                        int(bool(data.get("dim_enabled", False))),
                        float(data.get("dim_opacity", 0.0)),
                        int(bool(data.get("focus_enabled", False))),
                        now, profile_id,
                    ),
                )
            return True
        except sqlite3.Error as e:
            log.error("update_profile error: %s", e)
            return False

    def delete_profile(self, profile_id: int) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
            active = self.get_active_profile_id()
            if active == profile_id:
                remaining = self.list_profiles()
                if remaining:
                    self.set_active_profile(remaining[0]["id"])
                else:
                    self._meta_set("active_profile_id", "")
            return True
        except sqlite3.Error as e:
            log.error("delete_profile error: %s", e)
            return False

    def get_active_profile_id(self) -> Optional[int]:
        raw = self._meta_get("active_profile_id", "")
        if not raw:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def set_active_profile(self, profile_id: int) -> None:
        self._meta_set("active_profile_id", str(profile_id))

    def get_active_profile(self) -> Optional[dict]:
        pid = self.get_active_profile_id()
        if pid is None:
            return None
        return self.get_profile(pid)

    # ------------------------------------------------------------------
    # Screen time
    # ------------------------------------------------------------------

    def add_screen_minutes(self, minutes: int, day: Optional[date] = None) -> None:
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

    def set_eye_strain_score(self, score: int, day: Optional[date] = None) -> None:
        day_str = (day or date.today()).isoformat()
        score = max(0, min(100, int(score)))
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO daily_stats (stat_date, eye_strain_score)
                    VALUES (?, ?)
                    ON CONFLICT(stat_date) DO UPDATE SET
                        eye_strain_score = excluded.eye_strain_score
                    """,
                    (day_str, score),
                )
        except sqlite3.Error as e:
            log.error("set_eye_strain_score error: %s", e)

    # ------------------------------------------------------------------
    # Break tracking
    # ------------------------------------------------------------------

    def record_break_start(self, break_type: str = "20-20-20") -> int:
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
            "eye_strain_score": 0,
        }

    def get_weekly_stats(self) -> list[dict]:
        """Return last 7 calendar days, filling gaps with zeros."""
        today = date.today()
        start = today - timedelta(days=6)
        by_date: dict[str, dict] = {}
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM daily_stats WHERE stat_date >= ? ORDER BY stat_date ASC",
                    (start.isoformat(),),
                ).fetchall()
                by_date = {r["stat_date"]: dict(r) for r in rows}
        except sqlite3.Error as e:
            log.error("get_weekly_stats error: %s", e)

        filled: list[dict] = []
        for i in range(7):
            d = start + timedelta(days=i)
            key = d.isoformat()
            if key in by_date:
                filled.append(by_date[key])
            else:
                filled.append({
                    "stat_date": key,
                    "screen_minutes": 0,
                    "breaks_done": 0,
                    "breaks_missed": 0,
                    "posture_alerts": 0,
                    "eye_strain_score": 0,
                })
        return filled

    def get_break_streak(self) -> int:
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

    def db_path(self) -> Path:
        return self._db_path

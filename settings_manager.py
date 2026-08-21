"""
settings_manager.py - Configuration management for NeuroShield Eye.

Loads default_config.json from the bundled config/ directory, then overlays
the user's saved config from %APPDATA%/NeuroShieldEye/user_config.json.
Provides typed getters and a save() method. Thread-safe via a RLock.
"""

import copy
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Optional

from logger import get_logger

log = get_logger("settings_manager")

_EMBEDDED_DEFAULTS = {
    "app": {
        "start_with_windows": False,
        "minimize_to_tray": True,
        "show_notifications": True,
    },
    "blue_light": {
        "enabled": True,
        "color_temperature": 3400,
        "opacity": 0.35,
    },
    "break_timer": {
        "mode": "20-20-20",
        "work_interval_minutes": 20,
        "break_duration_seconds": 20,
        "forced_break": False,
        "sound_enabled": True,
        "custom_work_minutes": 45,
        "custom_break_minutes": 5,
    },
    "dim_engine": {
        "enabled": False,
        "opacity": 0.0,
    },
    "focus_mode": {
        "enabled": False,
        "dim_opacity": 0.6,
        "grayscale": False,
    },
    "posture": {
        "enabled": True,
        "interval_minutes": 30,
        "message": "Check your posture! Sit up straight and relax your shoulders.",
    },
    "analytics": {
        "track_screen_time": True,
        "daily_goal_hours": 8,
    },
}


def _get_user_config_path() -> Path:
    app_data = os.environ.get("APPDATA")
    if app_data:
        config_dir = Path(app_data) / "NeuroShieldEye"
    else:
        config_dir = Path.home() / ".NeuroShieldEye"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "user_config.json"


def _get_default_config_path() -> Optional[Path]:
    """Locate default_config.json in the flat tree or a frozen bundle."""
    here = Path(__file__).resolve().parent
    meipass = getattr(sys, "_MEIPASS", "")
    candidates = [
        here / "default_config.json",
        here / "config" / "default_config.json",
        Path(meipass) / "default_config.json" if meipass else None,
        Path(meipass) / "config" / "default_config.json" if meipass else None,
    ]
    for path in candidates:
        if path is not None and path.exists():
            return path
    return None


class SettingsManager:
    """
    Thread-safe configuration manager.

    Merges default config with user overrides. Exposes get/set/save/reset.
    All sections are validated against the default schema on load.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._defaults: dict = {}
        self._config: dict = {}
        self._user_path = _get_user_config_path()
        self._load()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get(self, section: str, key: str, fallback: Any = None) -> Any:
        """Return config value at config[section][key], with optional fallback."""
        with self._lock:
            try:
                return self._config[section][key]
            except KeyError:
                return fallback

    def set(self, section: str, key: str, value: Any) -> None:
        """Update a config value in memory. Call save() to persist."""
        with self._lock:
            if section not in self._config:
                self._config[section] = {}
            self._config[section][key] = value
            log.debug("Config set: [%s][%s] = %r", section, key, value)

    def get_section(self, section: str) -> dict:
        """Return a shallow copy of a config section."""
        with self._lock:
            return dict(self._config.get(section, {}))

    def save(self) -> None:
        """Persist current config to the user config file."""
        with self._lock:
            try:
                with open(self._user_path, "w", encoding="utf-8") as f:
                    json.dump(self._config, f, indent=2)
                log.info("Config saved → %s", self._user_path)
            except OSError as e:
                log.error("Failed to save config: %s", e)

    def reset_to_defaults(self) -> None:
        """Overwrite in-memory config with factory defaults and save."""
        with self._lock:
            self._config = copy.deepcopy(self._defaults)
            self.save()
            log.info("Config reset to defaults.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load defaults, then overlay user config if it exists."""
        with self._lock:
            # Load defaults
            try:
                default_path = _get_default_config_path()
                if default_path:
                    with open(default_path, "r", encoding="utf-8") as f:
                        self._defaults = json.load(f)
                    log.debug("Loaded defaults from %s", default_path)
                else:
                    self._defaults = copy.deepcopy(_EMBEDDED_DEFAULTS)
                    log.debug("Using embedded default config.")
            except (OSError, json.JSONDecodeError) as e:
                log.error("Cannot load default config: %s", e)
                self._defaults = copy.deepcopy(_EMBEDDED_DEFAULTS)

            self._config = copy.deepcopy(self._defaults)

            # Overlay user config
            if self._user_path.exists():
                try:
                    with open(self._user_path, "r", encoding="utf-8") as f:
                        user_cfg = json.load(f)
                    self._deep_merge(self._config, user_cfg)
                    log.info("User config loaded from %s", self._user_path)
                except (json.JSONDecodeError, OSError) as e:
                    log.warning("User config corrupt/unreadable (%s), using defaults.", e)

    def _deep_merge(self, base: dict, overlay: dict) -> None:
        """Recursively merge overlay into base, validating keys against defaults."""
        for key, value in overlay.items():
            if key not in base:
                log.warning("Unknown config key '%s' in user config — ignoring.", key)
                continue
            if isinstance(value, dict) and isinstance(base[key], dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

"""
settings_manager.py - Configuration management for NeuroShield Eye.

Loads default_config.json from the bundled config/ directory, then overlays
the user's saved config from %APPDATA%/NeuroShieldEye/user_config.json.
Provides typed getters and a save() method. Thread-safe via a RLock.
"""

import copy
import json
import os
import threading
from pathlib import Path
from typing import Any

from utils.logger import get_logger

log = get_logger("settings_manager")


def _get_user_config_path() -> Path:
    app_data = os.environ.get("APPDATA", Path.home())
    config_dir = Path(app_data) / "NeuroShieldEye"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "user_config.json"


def _get_default_config_path() -> Path:
    """Locate default_config.json relative to the project root or frozen exe."""
    # When running from source: NeuroShield-Eye/src/settings/settings_manager.py
    # default_config is at NeuroShield-Eye/config/default_config.json
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent.parent / "config" / "default_config.json",  # source tree
        Path(os.environ.get("_MEIPASS", "")) / "config" / "default_config.json",  # PyInstaller
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("default_config.json not found in any expected location.")


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
                with open(default_path, "r", encoding="utf-8") as f:
                    self._defaults = json.load(f)
                log.debug("Loaded defaults from %s", default_path)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                log.error("Cannot load default config: %s", e)
                self._defaults = {}

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

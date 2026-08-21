"""
main.py - Entry point and AppController for NeuroShield-Eye Pro.

Wires local PIN auth, the sidebar dashboard, overlay engines, and SQLite.
Overlays react immediately to UI toggles; persistence happens afterwards.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox
from PyQt6.QtCore import QTimer

app = QApplication(sys.argv)
app.setApplicationName("NeuroShieldEye")
app.setOrganizationName("NeuroShield")
app.setQuitOnLastWindowClosed(False)

from logger import setup_logging, get_logger
from settings_manager import SettingsManager
from database_manager import DatabaseManager
from tray_manager import TrayManager
from blue_light_overlay import BlueLightOverlay
from break_timer import BreakTimer
from dim_engine import DimEngine
from focus_mode import FocusMode
from posture_reminder import PostureReminder
from dashboard_window import DashboardWindow
from auth_window import AuthWindow

try:
    import winreg
except ImportError:  # non-Windows dev / CI
    winreg = None  # type: ignore

setup_logging()
log = get_logger("main")

_STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "NeuroShieldEye"


def _set_startup_registry(enable: bool) -> None:
    if winreg is None:
        log.debug("Startup registry skipped (not Windows).")
        return
    try:
        exe_path = sys.executable if getattr(sys, "frozen", False) else (
            f'"{sys.executable}" "{Path(__file__).resolve()}"'
        )
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enable:
                winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, exe_path)
                log.info("Added to startup registry.")
            else:
                try:
                    winreg.DeleteValue(key, _APP_NAME)
                    log.info("Removed from startup registry.")
                except FileNotFoundError:
                    pass
    except OSError as e:
        log.error("Registry operation failed: %s", e)


class AppController:
    """Owns engines, dashboard, and the signal graph between them."""

    def __init__(self, settings: SettingsManager, db: DatabaseManager) -> None:
        log.info("NeuroShield Eye Pro starting up...")
        self._settings = settings
        self._db = db

        self._tray = TrayManager()
        self._blue_light = BlueLightOverlay()
        self._break_timer = BreakTimer(self._settings, self._db)
        self._dim_engine = DimEngine()
        self._focus_mode = FocusMode(self._settings)
        self._posture = PostureReminder(self._settings, self._db)

        self._dashboard: DashboardWindow | None = None
        self._locked = False

        self._screen_time_timer = QTimer()
        self._screen_time_timer.setInterval(60_000)
        self._screen_time_timer.timeout.connect(self._track_screen_minute)

        self._connect_tray()
        self._apply_initial_settings()
        log.info("AppController initialized.")

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def _connect_tray(self) -> None:
        t = self._tray
        t.action_blue_light_toggled.connect(self._toggle_blue_light)
        t.action_break_now.connect(self._break_timer.trigger_break_now)
        t.action_focus_toggled.connect(self._toggle_focus)
        t.action_open_dashboard.connect(lambda: self.open_dashboard())
        t.action_open_settings.connect(lambda: self.open_dashboard("settings"))
        t.action_exit.connect(self._exit)

        self._break_timer.break_started.connect(self._on_break_started)
        self._break_timer.break_ended.connect(self._on_break_ended)

        instance = QApplication.instance()
        if instance:
            instance.screenAdded.connect(self._on_screens_changed)
            instance.screenRemoved.connect(self._on_screens_changed)

    def _connect_dashboard(self, dash: DashboardWindow) -> None:
        dash.blue_light_toggled.connect(self._on_ui_blue_light)
        dash.blue_light_preview.connect(self._on_ui_blue_preview)
        dash.dim_toggled.connect(self._on_ui_dim)
        dash.dim_preview.connect(self._on_ui_dim_preview)
        dash.focus_toggled.connect(self._on_ui_focus)
        dash.focus_preview.connect(self._on_ui_focus_preview)
        dash.break_now.connect(self._break_timer.trigger_break_now)
        dash.settings_changed.connect(self._apply_settings_changes)
        dash.profile_applied.connect(self._on_profile_applied)
        dash.lock_requested.connect(self._lock)

        self._break_timer.work_tick.connect(dash.update_work_tick)
        self._break_timer.break_started.connect(dash.on_break_started)
        self._break_timer.break_ended.connect(dash.on_break_ended)

        mode = self._settings.get("break_timer", "mode", "20-20-20")
        if mode == "20-20-20":
            total = int(self._settings.get("break_timer", "work_interval_minutes", 20)) * 60
        else:
            total = int(self._settings.get("break_timer", "custom_work_minutes", 45)) * 60
        dash.set_work_total(total)

    # ------------------------------------------------------------------
    # Initial configuration
    # ------------------------------------------------------------------

    def _apply_initial_settings(self) -> None:
        if self._settings.get("blue_light", "enabled", True):
            self._blue_light.apply_settings(
                temperature=self._settings.get("blue_light", "color_temperature", 3400),
                opacity=self._settings.get("blue_light", "opacity", 0.35),
            )
            self._blue_light.show()
            self._tray.update_blue_light_state(True)

        if self._settings.get("dim_engine", "enabled", False):
            self._dim_engine.set_opacity(self._settings.get("dim_engine", "opacity", 0.0))
            self._dim_engine.show()

        if self._settings.get("focus_mode", "enabled", False):
            self._focus_mode.enable()
            self._tray.update_focus_state(True)

        if self._settings.get("posture", "enabled", True):
            self._posture.start()

        _set_startup_registry(self._settings.get("app", "start_with_windows", False))
        self._break_timer.start()

        if self._settings.get("analytics", "track_screen_time", True):
            self._screen_time_timer.start()

    def _apply_settings_changes(self) -> None:
        log.info("Applying settings changes...")

        bl_enabled = self._settings.get("blue_light", "enabled", True)
        self._blue_light.apply_settings(
            temperature=self._settings.get("blue_light", "color_temperature", 3400),
            opacity=self._settings.get("blue_light", "opacity", 0.35),
        )
        if bl_enabled and not self._blue_light.is_visible():
            self._blue_light.show()
        elif not bl_enabled and self._blue_light.is_visible():
            self._blue_light.hide()
        self._tray.update_blue_light_state(bl_enabled)

        dim_enabled = self._settings.get("dim_engine", "enabled", False)
        self._dim_engine.set_opacity(self._settings.get("dim_engine", "opacity", 0.0))
        if dim_enabled and not self._dim_engine.is_visible():
            self._dim_engine.show()
        elif not dim_enabled and self._dim_engine.is_visible():
            self._dim_engine.hide()

        focus_enabled = self._settings.get("focus_mode", "enabled", False)
        if focus_enabled and not self._focus_mode.is_enabled():
            self._focus_mode.enable()
        elif not focus_enabled and self._focus_mode.is_enabled():
            self._focus_mode.disable()
        self._tray.update_focus_state(self._focus_mode.is_enabled())

        posture_enabled = self._settings.get("posture", "enabled", True)
        if posture_enabled and not self._posture.is_enabled():
            self._posture.start()
        elif not posture_enabled and self._posture.is_enabled():
            self._posture.stop()
        else:
            self._posture.update_interval()

        _set_startup_registry(self._settings.get("app", "start_with_windows", False))

        self._break_timer.stop()
        self._break_timer.start()
        if self._dashboard:
            minutes = int(self._settings.get("break_timer", "work_interval_minutes", 20))
            self._dashboard.set_work_total(minutes * 60)

        if self._settings.get("analytics", "track_screen_time", True):
            if not self._screen_time_timer.isActive():
                self._screen_time_timer.start()
        else:
            self._screen_time_timer.stop()

    # ------------------------------------------------------------------
    # Optimistic UI handlers (overlay first, disk later)
    # ------------------------------------------------------------------

    def _on_ui_blue_light(self, enabled: bool) -> None:
        if enabled:
            self._blue_light.show()
        else:
            self._blue_light.hide()
        self._tray.update_blue_light_state(enabled)

    def _on_ui_blue_preview(self, kelvin: int, opacity: float) -> None:
        self._blue_light.apply_settings(kelvin, opacity)
        if self._settings.get("blue_light", "enabled", True) and not self._blue_light.is_visible():
            self._blue_light.show()

    def _on_ui_dim(self, enabled: bool) -> None:
        if enabled:
            self._dim_engine.show()
        else:
            self._dim_engine.hide()

    def _on_ui_dim_preview(self, opacity: float) -> None:
        self._dim_engine.set_opacity(opacity)
        if self._settings.get("dim_engine", "enabled", False) and not self._dim_engine.is_visible():
            self._dim_engine.show()

    def _on_ui_focus(self, enabled: bool) -> None:
        if enabled:
            self._focus_mode.enable()
        else:
            self._focus_mode.disable()
        self._tray.update_focus_state(enabled)

    def _on_ui_focus_preview(self, opacity: float, grayscale: bool) -> None:
        self._focus_mode.update_params(opacity, grayscale)

    def _on_profile_applied(self, profile: dict) -> None:
        # Overlays already get the instant path from the dashboard sync + signals.
        self._settings.set("blue_light", "enabled", profile["blue_light_enabled"])
        self._settings.set("blue_light", "color_temperature", profile["color_temperature"])
        self._settings.set("blue_light", "opacity", profile["blue_light_opacity"])
        self._settings.set("dim_engine", "enabled", profile["dim_enabled"])
        self._settings.set("dim_engine", "opacity", profile["dim_opacity"])
        self._settings.set("focus_mode", "enabled", profile["focus_enabled"])

        self._blue_light.apply_settings(
            profile["color_temperature"], profile["blue_light_opacity"]
        )
        if profile["blue_light_enabled"]:
            self._blue_light.show()
        else:
            self._blue_light.hide()
        self._tray.update_blue_light_state(profile["blue_light_enabled"])

        self._dim_engine.set_opacity(profile["dim_opacity"])
        if profile["dim_enabled"]:
            self._dim_engine.show()
        else:
            self._dim_engine.hide()

        if profile["focus_enabled"]:
            self._focus_mode.enable()
        else:
            self._focus_mode.disable()
        self._tray.update_focus_state(profile["focus_enabled"])
        self._settings.save()
        log.info("Applied profile '%s'.", profile.get("name"))

    # ------------------------------------------------------------------
    # Tray handlers
    # ------------------------------------------------------------------

    def _toggle_blue_light(self) -> None:
        visible = self._blue_light.toggle()
        self._settings.set("blue_light", "enabled", visible)
        self._settings.save()
        self._tray.update_blue_light_state(visible)
        if self._dashboard:
            self._dashboard._set_checked_silent(self._dashboard._tog_bl, visible)
            self._dashboard._set_checked_silent(self._dashboard._live_bl, visible)
        state = "enabled" if visible else "disabled"
        if self._settings.get("app", "show_notifications", True):
            self._tray.show_notification("Blue Light Filter", f"Filter {state}.")

    def _toggle_focus(self) -> None:
        enabled = self._focus_mode.toggle()
        self._settings.set("focus_mode", "enabled", enabled)
        self._settings.save()
        self._tray.update_focus_state(enabled)
        if self._dashboard:
            self._dashboard._on_focus_toggled(enabled)

    def open_dashboard(self, page: str = "dashboard") -> None:
        if self._locked:
            auth = AuthWindow(self._db)
            if auth.exec() != QDialog.DialogCode.Accepted:
                return
            self._locked = False
        if self._dashboard is None:
            self._dashboard = DashboardWindow(self._db, self._settings)
            self._connect_dashboard(self._dashboard)
        self._dashboard.show()
        self._dashboard.raise_()
        self._dashboard.activateWindow()
        self._dashboard.show_page(page)

    def _lock(self) -> None:
        self._locked = True
        if self._dashboard:
            self._dashboard.hide()
        auth = AuthWindow(self._db)
        if auth.exec() != QDialog.DialogCode.Accepted:
            return
        self._locked = False
        self.open_dashboard()

    def _exit(self) -> None:
        log.info("Shutting down NeuroShield Eye...")
        self._break_timer.stop()
        self._posture.stop()
        self._focus_mode.disable()
        self._blue_light.hide()
        self._dim_engine.hide()
        self._tray.hide()
        self._screen_time_timer.stop()
        QApplication.quit()

    def _on_break_started(self) -> None:
        if self._settings.get("app", "show_notifications", True):
            self._tray.show_notification("Time for a Break!", "Look 20 feet away for 20 seconds.")

    def _on_break_ended(self, completed: bool) -> None:
        if completed and self._settings.get("app", "show_notifications", True):
            self._tray.show_notification("Break Complete", "Great job! Back to work.")

    def _track_screen_minute(self) -> None:
        self._db.add_screen_minutes(1)

    def _on_screens_changed(self) -> None:
        log.info("Screen configuration changed — refreshing overlays.")
        self._blue_light.refresh_monitors()
        self._dim_engine.refresh_monitors()
        self._focus_mode.refresh_monitors()


def _acquire_single_instance():
    lock_path = Path(tempfile.gettempdir()) / "neuroshield_eye.lock"
    lock_file = open(lock_path, "w")
    try:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        msg = QMessageBox()
        msg.setWindowTitle("NeuroShield Eye")
        msg.setText("NeuroShield Eye is already running.\nCheck your system tray.")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()
        sys.exit(0)
    return lock_file


def main() -> None:
    _lock = _acquire_single_instance()  # noqa: F841 — keep file handle alive

    db = DatabaseManager()
    settings = SettingsManager()

    auth = AuthWindow(db)
    if auth.exec() != QDialog.DialogCode.Accepted:
        log.info("Auth cancelled — exiting.")
        sys.exit(0)

    controller = AppController(settings, db)
    controller._tray.setup()
    controller.open_dashboard()

    log.info("NeuroShield Eye Pro running.")
    exit_code = app.exec()
    log.info("Application exited with code %d.", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

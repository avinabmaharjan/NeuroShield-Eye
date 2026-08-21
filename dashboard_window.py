"""
dashboard_window.py - Sidebar-driven main UI for NeuroShield-Eye Pro.

Pages: Dashboard · Eye Protection · Focus Mode · Analytics · Settings
Dark Material + Segoe UI. Optimistic overlay toggles. Profile CRUD.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import pyqtgraph as pg
from PyQt6.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from logger import get_logger

log = get_logger("dashboard_window")

pg.setConfigOption("background", "#161616")
pg.setConfigOption("foreground", "#9E9E9E")

_ACCENT = "#82B1FF"
_GREEN = "#69F0AE"
_AMBER = "#FFB74D"
_RED = "#EF5350"

_STYLE = """
QMainWindow, QWidget {
    background-color: #121212;
    color: #E6E1E5;
    font-family: 'Segoe UI';
}
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: transparent; width: 8px; margin: 4px 0;
}
QScrollBar::handle:vertical {
    background: #2C2C2C; border-radius: 4px; min-height: 32px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QLabel { background: transparent; }
QFrame#sidebar {
    background-color: #1A1A1A;
    border-right: 1px solid #2C2C2C;
}
QPushButton#nav {
    background: transparent;
    color: #9E9E9E;
    border: none;
    border-radius: 10px;
    text-align: left;
    padding: 10px 14px;
    font-size: 13px;
}
QPushButton#nav:hover { background: #242424; color: #E6E1E5; }
QPushButton#nav:checked {
    background-color: #1A237E;
    color: #82B1FF;
    font-weight: 600;
}
QPushButton#primary {
    background-color: #82B1FF;
    color: #0D1117;
    border: none;
    border-radius: 10px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton#primary:hover { background-color: #A7C8FF; }
QPushButton#ghost {
    background: #1E1E1E;
    color: #E6E1E5;
    border: 1px solid #2C2C2C;
    border-radius: 10px;
    padding: 8px 14px;
}
QPushButton#ghost:hover { border-color: #82B1FF; }
QPushButton#danger {
    background: transparent;
    color: #EF5350;
    border: 1px solid #EF5350;
    border-radius: 10px;
    padding: 8px 14px;
}
QPushButton#danger:hover { background: #3B1111; }
QPushButton#apply {
    background-color: #69F0AE;
    color: #0D1117;
    border: none;
    border-radius: 8px;
    padding: 6px 12px;
    font-weight: 600;
}
QFrame#card {
    background-color: #1E1E1E;
    border: 1px solid #2C2C2C;
    border-radius: 14px;
}
QFrame#empty {
    background-color: #1A1A1A;
    border: 1px dashed #3A3A3A;
    border-radius: 14px;
}
QLineEdit, QTextEdit, QSpinBox {
    background-color: #1E1E1E;
    border: 1px solid #2C2C2C;
    border-radius: 8px;
    padding: 8px 10px;
    color: #E6E1E5;
    selection-background-color: #1A237E;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus { border-color: #82B1FF; }
QSlider::groove:horizontal {
    height: 4px; background: #2C2C2C; border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #82B1FF; width: 16px; height: 16px;
    margin: -6px 0; border-radius: 8px;
}
QSlider::sub-page:horizontal { background: #82B1FF; border-radius: 2px; }
QCheckBox { color: #E6E1E5; spacing: 8px; }
QCheckBox::indicator {
    width: 18px; height: 18px; border-radius: 4px;
    border: 1px solid #3A3A3A; background: #1E1E1E;
}
QCheckBox::indicator:checked { background: #82B1FF; border-color: #82B1FF; }
QProgressBar {
    background: #2C2C2C; border: none; border-radius: 6px; height: 10px;
    text-align: center;
}
QProgressBar::chunk { background-color: #69F0AE; border-radius: 6px; }
"""


def _label(text: str, size: int = 13, bold: bool = False, color: str = "#E6E1E5") -> QLabel:
    lbl = QLabel(text)
    weight = QFont.Weight.Bold if bold else QFont.Weight.Normal
    lbl.setFont(QFont("Segoe UI", size, weight))
    lbl.setStyleSheet(f"color: {color};")
    lbl.setWordWrap(True)
    return lbl


class Spinner(QWidget):
    """Small indeterminate arc spinner used for loading states."""

    def __init__(self, parent=None, size: int = 36) -> None:
        super().__init__(parent)
        self._angle = 0
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def _tick(self) -> None:
        self._angle = (self._angle + 8) % 360
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(_ACCENT), 3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        m = 4
        painter.drawArc(QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m),
                        self._angle * 16, 270 * 16)


class EmptyState(QFrame):
    def __init__(self, title: str, body: str, cta: str = "", on_cta=None) -> None:
        super().__init__()
        self.setObjectName("empty")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 36, 32, 36)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(_label(title, 16, True), alignment=Qt.AlignmentFlag.AlignCenter)
        body_l = _label(body, 11, color="#9E9E9E")
        body_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(body_l)
        if cta and on_cta:
            btn = QPushButton(cta)
            btn.setObjectName("primary")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedWidth(220)
            btn.clicked.connect(on_cta)
            layout.addSpacing(8)
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)


class StatCard(QFrame):
    def __init__(self, title: str, value: str, unit: str = "", accent: str = _ACCENT) -> None:
        super().__init__()
        self.setObjectName("card")
        self.setMinimumHeight(108)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        layout.addWidget(_label(title.upper(), 9, True, "#9E9E9E"))
        row = QHBoxLayout()
        self._value = QLabel(value)
        self._value.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self._value.setStyleSheet(f"color: {accent};")
        row.addWidget(self._value)
        if unit:
            u = _label(unit, 11, color="#9E9E9E")
            u.setAlignment(Qt.AlignmentFlag.AlignBottom)
            row.addWidget(u)
        row.addStretch()
        layout.addLayout(row)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class ProfileEditorDialog(QDialog):
    """Create / update a protection profile."""

    def __init__(self, parent=None, profile: Optional[dict] = None) -> None:
        super().__init__(parent)
        self._profile = profile or {}
        editing = bool(profile)
        self.setWindowTitle("Edit profile" if editing else "New protection profile")
        self.setModal(True)
        self.setMinimumSize(440, 520)
        self.setStyleSheet(_STYLE)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(10)

        root.addWidget(_label("Name", 10, True, "#9E9E9E"))
        self.name = QLineEdit(self._profile.get("name", ""))
        self.name.setPlaceholderText("e.g. Late Night Coding")
        root.addWidget(self.name)

        root.addWidget(_label("Description", 10, True, "#9E9E9E"))
        self.desc = QTextEdit(self._profile.get("description", ""))
        self.desc.setFixedHeight(70)
        root.addWidget(self.desc)

        self.bl_on = QCheckBox("Blue light filter")
        self.bl_on.setChecked(bool(self._profile.get("blue_light_enabled", 1)))
        root.addWidget(self.bl_on)

        self.temp = QSlider(Qt.Orientation.Horizontal)
        self.temp.setRange(2000, 6500)
        self.temp.setValue(int(self._profile.get("color_temperature", 3400)))
        self.temp_lbl = _label(f"{self.temp.value()}K", 10, color="#82B1FF")
        self.temp.valueChanged.connect(lambda v: self.temp_lbl.setText(f"{v}K"))
        trow = QHBoxLayout()
        trow.addWidget(_label("Temperature", 10, color="#9E9E9E"))
        trow.addStretch()
        trow.addWidget(self.temp_lbl)
        root.addLayout(trow)
        root.addWidget(self.temp)

        self.bl_op = QSlider(Qt.Orientation.Horizontal)
        self.bl_op.setRange(0, 80)
        self.bl_op.setValue(int(float(self._profile.get("blue_light_opacity", 0.35)) * 100))
        self.bl_op_lbl = _label(f"{self.bl_op.value()}%", 10, color="#82B1FF")
        self.bl_op.valueChanged.connect(lambda v: self.bl_op_lbl.setText(f"{v}%"))
        orow = QHBoxLayout()
        orow.addWidget(_label("Filter strength", 10, color="#9E9E9E"))
        orow.addStretch()
        orow.addWidget(self.bl_op_lbl)
        root.addLayout(orow)
        root.addWidget(self.bl_op)

        self.dim_on = QCheckBox("Software dim")
        self.dim_on.setChecked(bool(self._profile.get("dim_enabled", 0)))
        root.addWidget(self.dim_on)

        self.dim_op = QSlider(Qt.Orientation.Horizontal)
        self.dim_op.setRange(0, 90)
        self.dim_op.setValue(int(float(self._profile.get("dim_opacity", 0.0)) * 100))
        self.dim_lbl = _label(f"{self.dim_op.value()}%", 10, color="#82B1FF")
        self.dim_op.valueChanged.connect(lambda v: self.dim_lbl.setText(f"{v}%"))
        drow = QHBoxLayout()
        drow.addWidget(_label("Dim level", 10, color="#9E9E9E"))
        drow.addStretch()
        drow.addWidget(self.dim_lbl)
        root.addLayout(drow)
        root.addWidget(self.dim_op)

        self.focus_on = QCheckBox("Focus mode (visual anchor)")
        self.focus_on.setChecked(bool(self._profile.get("focus_enabled", 0)))
        root.addWidget(self.focus_on)
        root.addStretch()

        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save profile")
        save.setObjectName("primary")
        save.clicked.connect(self._accept)
        btns.addWidget(cancel)
        btns.addStretch()
        btns.addWidget(save)
        root.addLayout(btns)

    def _accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Name required", "Give this profile a short name.")
            return
        self.accept()

    def data(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "description": self.desc.toPlainText().strip(),
            "blue_light_enabled": self.bl_on.isChecked(),
            "color_temperature": self.temp.value(),
            "blue_light_opacity": self.bl_op.value() / 100.0,
            "dim_enabled": self.dim_on.isChecked(),
            "dim_opacity": self.dim_op.value() / 100.0,
            "focus_enabled": self.focus_on.isChecked(),
        }


class DashboardWindow(QMainWindow):
    """Main application chrome: sidebar + stacked pages."""

    blue_light_toggled = pyqtSignal(bool)
    blue_light_preview = pyqtSignal(int, float)  # kelvin, opacity
    dim_toggled = pyqtSignal(bool)
    dim_preview = pyqtSignal(float)
    focus_toggled = pyqtSignal(bool)
    focus_preview = pyqtSignal(float, bool)  # opacity, grayscale
    break_now = pyqtSignal()
    settings_changed = pyqtSignal()
    profile_applied = pyqtSignal(dict)
    lock_requested = pyqtSignal()

    PAGES = [
        ("dashboard", "Dashboard"),
        ("protect", "Eye Protection"),
        ("focus", "Focus Mode"),
        ("analytics", "Analytics"),
        ("settings", "Settings"),
    ]

    def __init__(self, db, settings) -> None:
        super().__init__()
        self._db = db
        self._settings = settings
        self._page_index = {key: i for i, (key, _) in enumerate(self.PAGES)}
        self._nav_buttons: dict[str, QPushButton] = {}
        self._work_total = 20 * 60
        self._analytics_loaded = False
        self._persist_timer = QTimer(self)
        self._persist_timer.setSingleShot(True)
        self._persist_timer.timeout.connect(self._flush_settings)

        self.setWindowTitle("NeuroShield Eye Pro")
        self.setMinimumSize(1080, 700)
        self.resize(1180, 760)
        self.setStyleSheet(_STYLE)

        self._build_chrome()
        self._refresh_all()

    # ------------------------------------------------------------------
    # Chrome
    # ------------------------------------------------------------------

    def _build_chrome(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        split = QHBoxLayout(root)
        split.setContentsMargins(0, 0, 0, 0)
        split.setSpacing(0)

        split.addWidget(self._build_sidebar())

        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(0)
        right_l.addWidget(self._build_header())

        self._stack = QStackedWidget()
        self._stack.addWidget(self._wrap_scroll(self._build_dashboard_page()))
        self._stack.addWidget(self._wrap_scroll(self._build_protect_page()))
        self._stack.addWidget(self._wrap_scroll(self._build_focus_page()))
        self._stack.addWidget(self._wrap_scroll(self._build_analytics_page()))
        self._stack.addWidget(self._wrap_scroll(self._build_settings_page()))
        right_l.addWidget(self._stack, 1)
        split.addWidget(right, 1)

    def _build_sidebar(self) -> QFrame:
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(228)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(16, 22, 16, 16)
        layout.setSpacing(6)

        brand = _label("NEUROSHIELD", 9, True, _ACCENT)
        layout.addWidget(brand)
        layout.addWidget(_label("Eye Pro  ·  ADHD Edition", 10, color="#9E9E9E"))
        layout.addSpacing(18)

        for key, title in self.PAGES:
            btn = QPushButton(title)
            btn.setObjectName("nav")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(42)
            btn.clicked.connect(lambda _=False, k=key: self.show_page(k))
            layout.addWidget(btn)
            self._nav_buttons[key] = btn

        layout.addStretch()

        self._focus_pill = QPushButton("Focus  ·  Off")
        self._focus_pill.setObjectName("ghost")
        self._focus_pill.setCursor(Qt.CursorShape.PointingHandCursor)
        self._focus_pill.clicked.connect(self._quick_toggle_focus)
        layout.addWidget(self._focus_pill)

        lock = QPushButton("Lock")
        lock.setObjectName("ghost")
        lock.setCursor(Qt.CursorShape.PointingHandCursor)
        lock.clicked.connect(self.lock_requested.emit)
        layout.addWidget(lock)
        return side

    def _build_header(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(64)
        bar.setStyleSheet("background: #121212; border-bottom: 1px solid #2C2C2C;")
        row = QHBoxLayout(bar)
        row.setContentsMargins(28, 0, 24, 0)
        self._header_title = _label("Dashboard", 18, True)
        row.addWidget(self._header_title)
        row.addStretch()
        user = self._db.get_user() or {}
        self._user_chip = _label(user.get("display_name", ""), 11, color="#9E9E9E")
        row.addWidget(self._user_chip)
        return bar

    def _wrap_scroll(self, inner: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(28, 22, 28, 28)
        lay.addWidget(inner)
        lay.addStretch()
        scroll.setWidget(host)
        return scroll

    def show_page(self, key: str) -> None:
        idx = self._page_index.get(key, 0)
        self._stack.setCurrentIndex(idx)
        title = dict(self.PAGES).get(key, "Dashboard")
        self._header_title.setText(title)
        for k, btn in self._nav_buttons.items():
            btn.setChecked(k == key)
        if key == "analytics":
            self._load_analytics_with_spinner()
        if key == "protect":
            self._render_profiles()
        if key == "dashboard":
            self._refresh_dashboard_stats()

    # ------------------------------------------------------------------
    # Dashboard page
    # ------------------------------------------------------------------

    def _build_dashboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self._greet = _label("Good focus session.", 14, color="#9E9E9E")
        layout.addWidget(self._greet)

        # 20-20-20 gamified card
        self._break_card = QFrame()
        self._break_card.setObjectName("card")
        bc = QVBoxLayout(self._break_card)
        bc.setContentsMargins(20, 18, 20, 18)
        top = QHBoxLayout()
        top.addWidget(_label("20-20-20 visual cue", 12, True))
        top.addStretch()
        now_btn = QPushButton("Take a break now")
        now_btn.setObjectName("ghost")
        now_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        now_btn.clicked.connect(self.break_now.emit)
        top.addWidget(now_btn)
        bc.addLayout(top)
        self._break_hint = _label("Next look-away in —", 11, color="#9E9E9E")
        bc.addWidget(self._break_hint)
        self._break_bar = QProgressBar()
        self._break_bar.setRange(0, 1000)
        self._break_bar.setValue(0)
        self._break_bar.setTextVisible(False)
        self._break_bar.setFixedHeight(12)
        bc.addWidget(self._break_bar)
        self._streak_lbl = _label("Break streak: 0 days", 10, color=_AMBER)
        bc.addWidget(self._streak_lbl)
        layout.addWidget(self._break_card)

        cards = QGridLayout()
        cards.setSpacing(12)
        self._card_time = StatCard("Screen time today", "0", "min", _ACCENT)
        self._card_done = StatCard("Breaks completed", "0", "", _GREEN)
        self._card_miss = StatCard("Breaks missed", "0", "", _RED)
        self._card_strain = StatCard("Eye strain", "0", "/ 100", _AMBER)
        cards.addWidget(self._card_time, 0, 0)
        cards.addWidget(self._card_done, 0, 1)
        cards.addWidget(self._card_miss, 0, 2)
        cards.addWidget(self._card_strain, 0, 3)
        layout.addLayout(cards)

        # Quick toggles — optimistic
        toggles = QFrame()
        toggles.setObjectName("card")
        tg = QHBoxLayout(toggles)
        tg.setContentsMargins(20, 16, 20, 16)
        tg.addWidget(_label("Quick filters", 12, True))
        tg.addStretch()
        self._tog_bl = QCheckBox("Blue light")
        self._tog_dim = QCheckBox("Dim")
        self._tog_focus = QCheckBox("Focus")
        self._tog_bl.setChecked(bool(self._settings.get("blue_light", "enabled", True)))
        self._tog_dim.setChecked(bool(self._settings.get("dim_engine", "enabled", False)))
        self._tog_focus.setChecked(bool(self._settings.get("focus_mode", "enabled", False)))
        self._tog_bl.toggled.connect(self._on_bl_toggled)
        self._tog_dim.toggled.connect(self._on_dim_toggled)
        self._tog_focus.toggled.connect(self._on_focus_toggled)
        tg.addWidget(self._tog_bl)
        tg.addWidget(self._tog_dim)
        tg.addWidget(self._tog_focus)
        layout.addWidget(toggles)

        self._active_profile_lbl = _label("Active profile: —", 11, color="#9E9E9E")
        layout.addWidget(self._active_profile_lbl)
        return page

    def _refresh_dashboard_stats(self) -> None:
        user = self._db.get_user() or {}
        name = user.get("display_name", "")
        today = date.today().strftime("%A, %B %d")
        self._greet.setText(f"Hi {name}.  {today}  ·  keep the map simple, one thing at a time.")
        stats = self._db.get_today_stats()
        self._card_time.set_value(str(stats.get("screen_minutes", 0)))
        self._card_done.set_value(str(stats.get("breaks_done", 0)))
        self._card_miss.set_value(str(stats.get("breaks_missed", 0)))
        self._card_strain.set_value(str(stats.get("eye_strain_score", 0)))
        streak = self._db.get_break_streak()
        self._streak_lbl.setText(f"Break streak: {streak} day{'s' if streak != 1 else ''}  ·  look 20 ft away, 20 seconds.")
        active = self._db.get_active_profile()
        if active:
            self._active_profile_lbl.setText(f"Active profile: {active['name']}")
        else:
            self._active_profile_lbl.setText("Active profile: none — create one in Eye Protection.")
        self._sync_focus_pill()

    # ------------------------------------------------------------------
    # Eye protection + CRUD
    # ------------------------------------------------------------------

    def _build_protect_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        live = QFrame()
        live.setObjectName("card")
        ll = QVBoxLayout(live)
        ll.setContentsMargins(20, 18, 20, 18)
        ll.addWidget(_label("Live overlay  ·  changes apply instantly", 12, True))

        self._live_bl = QCheckBox("Blue light filter")
        self._live_bl.setChecked(bool(self._settings.get("blue_light", "enabled", True)))
        self._live_bl.toggled.connect(self._on_bl_toggled)
        ll.addWidget(self._live_bl)

        self._live_temp = QSlider(Qt.Orientation.Horizontal)
        self._live_temp.setRange(2000, 6500)
        self._live_temp.setValue(int(self._settings.get("blue_light", "color_temperature", 3400)))
        self._live_temp_lbl = _label(f"{self._live_temp.value()}K", 10, color=_ACCENT)
        trow = QHBoxLayout()
        trow.addWidget(_label("Color temperature", 10, color="#9E9E9E"))
        trow.addStretch()
        trow.addWidget(self._live_temp_lbl)
        ll.addLayout(trow)
        ll.addWidget(self._live_temp)
        self._live_temp.valueChanged.connect(self._on_temp_preview)

        self._live_op = QSlider(Qt.Orientation.Horizontal)
        self._live_op.setRange(0, 80)
        self._live_op.setValue(int(float(self._settings.get("blue_light", "opacity", 0.35)) * 100))
        self._live_op_lbl = _label(f"{self._live_op.value()}%", 10, color=_ACCENT)
        orow = QHBoxLayout()
        orow.addWidget(_label("Filter strength", 10, color="#9E9E9E"))
        orow.addStretch()
        orow.addWidget(self._live_op_lbl)
        ll.addLayout(orow)
        ll.addWidget(self._live_op)
        self._live_op.valueChanged.connect(self._on_op_preview)

        self._live_dim = QCheckBox("Software dim")
        self._live_dim.setChecked(bool(self._settings.get("dim_engine", "enabled", False)))
        self._live_dim.toggled.connect(self._on_dim_toggled)
        ll.addWidget(self._live_dim)

        self._live_dim_op = QSlider(Qt.Orientation.Horizontal)
        self._live_dim_op.setRange(0, 90)
        self._live_dim_op.setValue(int(float(self._settings.get("dim_engine", "opacity", 0.0)) * 100))
        self._live_dim_lbl = _label(f"{self._live_dim_op.value()}%", 10, color=_ACCENT)
        drow = QHBoxLayout()
        drow.addWidget(_label("Dim level", 10, color="#9E9E9E"))
        drow.addStretch()
        drow.addWidget(self._live_dim_lbl)
        ll.addLayout(drow)
        ll.addWidget(self._live_dim_op)
        self._live_dim_op.valueChanged.connect(self._on_dim_preview)
        layout.addWidget(live)

        head = QHBoxLayout()
        head.addWidget(_label("Protection profiles", 14, True))
        head.addStretch()
        add = QPushButton("New profile")
        add.setObjectName("primary")
        add.setCursor(Qt.CursorShape.PointingHandCursor)
        add.clicked.connect(self._create_profile)
        head.addWidget(add)
        layout.addLayout(head)

        self._profile_host = QVBoxLayout()
        self._profile_host.setSpacing(10)
        holder = QWidget()
        holder.setLayout(self._profile_host)
        layout.addWidget(holder)
        return page

    def _render_profiles(self) -> None:
        while self._profile_host.count():
            item = self._profile_host.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        profiles = self._db.list_profiles()
        if not profiles:
            empty = EmptyState(
                "No profiles found. Create your first one!",
                "Profiles remember a filter setup so you never have to fiddle mid-flow.\n"
                "Try “Late Night Coding” or “Gaming Mode”.",
                "Create profile",
                self._create_profile,
            )
            self._profile_host.addWidget(empty)
            return

        active_id = self._db.get_active_profile_id()
        for p in profiles:
            self._profile_host.addWidget(self._profile_card(p, p["id"] == active_id))

    def _profile_card(self, p: dict, active: bool) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        if active:
            card.setStyleSheet("QFrame#card { border: 1px solid #82B1FF; }")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        title_row = QHBoxLayout()
        title_row.addWidget(_label(p["name"], 13, True))
        if active:
            badge = _label("ACTIVE", 9, True, _GREEN)
            title_row.addWidget(badge)
        title_row.addStretch()
        lay.addLayout(title_row)
        desc = p.get("description") or "No description."
        lay.addWidget(_label(desc, 10, color="#9E9E9E"))
        meta = (
            f"{'Blue light on' if p.get('blue_light_enabled') else 'Blue light off'}"
            f"  ·  {p.get('color_temperature', 3400)}K"
            f"  ·  dim {int(float(p.get('dim_opacity', 0)) * 100)}%"
            f"  ·  {'focus on' if p.get('focus_enabled') else 'focus off'}"
        )
        lay.addWidget(_label(meta, 10, color="#6E6E6E"))
        actions = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("apply")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(lambda _=False, pid=p["id"]: self._apply_profile(pid))
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("ghost")
        edit_btn.clicked.connect(lambda _=False, pid=p["id"]: self._edit_profile(pid))
        del_btn = QPushButton("Delete")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(lambda _=False, pid=p["id"]: self._delete_profile(pid))
        actions.addWidget(apply_btn)
        actions.addWidget(edit_btn)
        actions.addWidget(del_btn)
        actions.addStretch()
        lay.addLayout(actions)
        return card

    def _create_profile(self) -> None:
        dlg = ProfileEditorDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_id = self._db.create_profile(dlg.data())
        self._render_profiles()
        if new_id:
            log.info("Profile created id=%s", new_id)

    def _edit_profile(self, profile_id: int) -> None:
        existing = self._db.get_profile(profile_id)
        if not existing:
            return
        dlg = ProfileEditorDialog(self, existing)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._db.update_profile(profile_id, dlg.data())
        if self._db.get_active_profile_id() == profile_id:
            self._apply_profile(profile_id)
        else:
            self._render_profiles()

    def _delete_profile(self, profile_id: int) -> None:
        p = self._db.get_profile(profile_id)
        if not p:
            return
        box = QMessageBox(self)
        box.setWindowTitle("Delete profile")
        box.setText(f"Delete “{p['name']}”? This cannot be undone.")
        box.setStandardButtons(QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        self._db.delete_profile(profile_id)
        self._render_profiles()
        self._refresh_dashboard_stats()

    def _apply_profile(self, profile_id: int) -> None:
        p = self._db.get_profile(profile_id)
        if not p:
            return
        # Optimistic: paint overlays before SQLite confirms.
        payload = {
            "id": p["id"],
            "name": p["name"],
            "blue_light_enabled": bool(p["blue_light_enabled"]),
            "color_temperature": int(p["color_temperature"]),
            "blue_light_opacity": float(p["blue_light_opacity"]),
            "dim_enabled": bool(p["dim_enabled"]),
            "dim_opacity": float(p["dim_opacity"]),
            "focus_enabled": bool(p["focus_enabled"]),
        }
        self._sync_toggles_from_profile(payload)
        self.profile_applied.emit(payload)
        self._db.set_active_profile(profile_id)
        self._render_profiles()
        self._refresh_dashboard_stats()

    def _sync_toggles_from_profile(self, p: dict) -> None:
        self._set_checked_silent(self._tog_bl, p["blue_light_enabled"])
        self._set_checked_silent(self._live_bl, p["blue_light_enabled"])
        self._set_checked_silent(self._tog_dim, p["dim_enabled"])
        self._set_checked_silent(self._live_dim, p["dim_enabled"])
        self._set_checked_silent(self._tog_focus, p["focus_enabled"])
        self._set_checked_silent(self._focus_enable, p["focus_enabled"])
        self._live_temp.blockSignals(True)
        self._live_temp.setValue(p["color_temperature"])
        self._live_temp.blockSignals(False)
        self._live_temp_lbl.setText(f"{p['color_temperature']}K")
        self._live_op.blockSignals(True)
        self._live_op.setValue(int(p["blue_light_opacity"] * 100))
        self._live_op.blockSignals(False)
        self._live_op_lbl.setText(f"{int(p['blue_light_opacity'] * 100)}%")
        self._live_dim_op.blockSignals(True)
        self._live_dim_op.setValue(int(p["dim_opacity"] * 100))
        self._live_dim_op.blockSignals(False)
        self._live_dim_lbl.setText(f"{int(p['dim_opacity'] * 100)}%")
        self._sync_focus_pill()

    # ------------------------------------------------------------------
    # Focus page
    # ------------------------------------------------------------------

    def _build_focus_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("card")
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(22, 20, 22, 20)
        hl.addWidget(_label("Visual anchor", 16, True))
        hl.addWidget(_label(
            "ADHD brains notice every other window. Focus Mode dims everything "
            "except the window you are actually using, so the rest of the desktop "
            "stops competing for attention.",
            11, color="#9E9E9E",
        ))
        self._focus_enable = QCheckBox("Enable Focus Mode")
        self._focus_enable.setChecked(bool(self._settings.get("focus_mode", "enabled", False)))
        self._focus_enable.toggled.connect(self._on_focus_toggled)
        hl.addWidget(self._focus_enable)
        layout.addWidget(hero)

        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 18, 20, 18)
        self._focus_op = QSlider(Qt.Orientation.Horizontal)
        self._focus_op.setRange(20, 90)
        self._focus_op.setValue(int(float(self._settings.get("focus_mode", "dim_opacity", 0.6)) * 100))
        self._focus_op_lbl = _label(f"{self._focus_op.value()}%", 10, color=_ACCENT)
        row = QHBoxLayout()
        row.addWidget(_label("Surround dim", 10, color="#9E9E9E"))
        row.addStretch()
        row.addWidget(self._focus_op_lbl)
        cl.addLayout(row)
        cl.addWidget(self._focus_op)
        self._focus_op.valueChanged.connect(self._on_focus_preview)

        self._focus_gray = QCheckBox("Grayscale the background (extra calm)")
        self._focus_gray.setChecked(bool(self._settings.get("focus_mode", "grayscale", False)))
        self._focus_gray.toggled.connect(self._on_focus_preview)
        cl.addWidget(self._focus_gray)
        layout.addWidget(card)
        return page

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def _build_analytics_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self._analytics_spinner_row = QWidget()
        sp = QHBoxLayout(self._analytics_spinner_row)
        sp.setContentsMargins(0, 12, 0, 12)
        sp.addStretch()
        sp.addWidget(Spinner(self._analytics_spinner_row))
        sp.addWidget(_label("Loading your week…", 11, color="#9E9E9E"))
        sp.addStretch()
        layout.addWidget(self._analytics_spinner_row)

        self._analytics_body = QWidget()
        body = QVBoxLayout(self._analytics_body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(14)

        grid = QGridLayout()
        grid.setSpacing(12)
        self._a_time = StatCard("This week", "0", "hrs", _ACCENT)
        self._a_streak = StatCard("Streak", "0", "days", _AMBER)
        self._a_all = StatCard("All-time", "0", "hrs", _GREEN)
        grid.addWidget(self._a_time, 0, 0)
        grid.addWidget(self._a_streak, 0, 1)
        grid.addWidget(self._a_all, 0, 2)
        body.addLayout(grid)

        body.addWidget(_label("Screen time (minutes)", 13, True))
        self._time_chart = pg.PlotWidget()
        self._time_chart.setMinimumHeight(210)
        self._time_chart.showGrid(y=True, alpha=0.25)
        self._time_chart.setMouseEnabled(x=False, y=False)
        self._time_chart.setMenuEnabled(False)
        body.addWidget(self._time_chart)

        body.addWidget(_label("Eye strain score", 13, True))
        self._strain_chart = pg.PlotWidget()
        self._strain_chart.setMinimumHeight(210)
        self._strain_chart.showGrid(y=True, alpha=0.25)
        self._strain_chart.setMouseEnabled(x=False, y=False)
        self._strain_chart.setMenuEnabled(False)
        body.addWidget(self._strain_chart)

        body.addWidget(_label("Breaks completed vs missed", 13, True))
        self._break_chart = pg.PlotWidget()
        self._break_chart.setMinimumHeight(210)
        self._break_chart.showGrid(y=True, alpha=0.25)
        self._break_chart.setMouseEnabled(x=False, y=False)
        self._break_chart.setMenuEnabled(False)
        body.addWidget(self._break_chart)

        self._analytics_empty = EmptyState(
            "No analytics yet",
            "Keep NeuroShield running and your week will fill in here.",
        )
        self._analytics_empty.hide()
        body.addWidget(self._analytics_empty)

        self._analytics_body.hide()
        layout.addWidget(self._analytics_body)
        return page

    def _load_analytics_with_spinner(self) -> None:
        self._analytics_spinner_row.show()
        self._analytics_body.hide()
        QTimer.singleShot(280, self._fill_analytics)

    def _fill_analytics(self) -> None:
        weekly = self._db.get_weekly_stats()
        self._analytics_spinner_row.hide()
        self._analytics_body.show()
        self._analytics_loaded = True

        has_data = any(
            r.get("screen_minutes", 0) or r.get("breaks_done", 0) for r in weekly
        )
        self._analytics_empty.setVisible(not has_data)
        self._time_chart.setVisible(has_data)
        self._strain_chart.setVisible(has_data)
        self._break_chart.setVisible(has_data)

        week_min = sum(r.get("screen_minutes", 0) for r in weekly)
        self._a_time.set_value(str(round(week_min / 60, 1)))
        self._a_streak.set_value(str(self._db.get_break_streak()))
        self._a_all.set_value(str(self._db.get_all_time_total_hours()))
        if not has_data:
            return

        x = list(range(len(weekly)))
        labels = [r.get("stat_date", "")[-5:] for r in weekly]

        self._time_chart.clear()
        mins = [r.get("screen_minutes", 0) for r in weekly]
        self._time_chart.addItem(pg.BarGraphItem(
            x=x, height=mins, width=0.6, brush=QColor(_ACCENT), pen=pg.mkPen(None)
        ))
        self._time_chart.getAxis("bottom").setTicks([list(zip(x, labels))])

        self._strain_chart.clear()
        strain = [r.get("eye_strain_score", 0) for r in weekly]
        self._strain_chart.addItem(pg.BarGraphItem(
            x=x, height=strain, width=0.6, brush=QColor(_AMBER), pen=pg.mkPen(None)
        ))
        self._strain_chart.getAxis("bottom").setTicks([list(zip(x, labels))])

        self._break_chart.clear()
        done = [r.get("breaks_done", 0) for r in weekly]
        missed = [r.get("breaks_missed", 0) for r in weekly]
        self._break_chart.addItem(pg.BarGraphItem(
            x=x, height=done, width=0.35, brush=QColor(_GREEN), pen=pg.mkPen(None)
        ))
        self._break_chart.addItem(pg.BarGraphItem(
            x=[i + 0.38 for i in x], height=missed, width=0.35,
            brush=QColor(_RED), pen=pg.mkPen(None)
        ))
        self._break_chart.getAxis("bottom").setTicks([list(zip(x, labels))])

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        auth = QFrame()
        auth.setObjectName("card")
        al = QVBoxLayout(auth)
        al.setContentsMargins(20, 18, 20, 18)
        al.addWidget(_label("Local profile", 13, True))
        al.addWidget(_label("PIN is hashed with PBKDF2 and never leaves this PC.", 10, color="#9E9E9E"))
        self._set_name = QLineEdit((self._db.get_user() or {}).get("display_name", ""))
        al.addWidget(self._set_name)
        name_btn = QPushButton("Save name")
        name_btn.setObjectName("ghost")
        name_btn.clicked.connect(self._save_name)
        al.addWidget(name_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        al.addWidget(_label("Change PIN", 11, True, "#9E9E9E"))
        self._old_pin = QLineEdit()
        self._old_pin.setEchoMode(QLineEdit.EchoMode.Password)
        self._old_pin.setPlaceholderText("Current PIN")
        self._old_pin.setMaxLength(6)
        self._new_pin = QLineEdit()
        self._new_pin.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_pin.setPlaceholderText("New PIN (4–6 digits)")
        self._new_pin.setMaxLength(6)
        al.addWidget(self._old_pin)
        al.addWidget(self._new_pin)
        pin_btn = QPushButton("Update PIN")
        pin_btn.setObjectName("ghost")
        pin_btn.clicked.connect(self._save_pin)
        al.addWidget(pin_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        self._pin_status = _label("", 10, color=_GREEN)
        al.addWidget(self._pin_status)
        layout.addWidget(auth)

        gen = QFrame()
        gen.setObjectName("card")
        gl = QVBoxLayout(gen)
        gl.setContentsMargins(20, 18, 20, 18)
        gl.addWidget(_label("General", 13, True))
        self._start_win = QCheckBox("Start with Windows")
        self._notify = QCheckBox("Tray notifications")
        self._track = QCheckBox("Track screen time")
        self._start_win.setChecked(bool(self._settings.get("app", "start_with_windows", False)))
        self._notify.setChecked(bool(self._settings.get("app", "show_notifications", True)))
        self._track.setChecked(bool(self._settings.get("analytics", "track_screen_time", True)))
        gl.addWidget(self._start_win)
        gl.addWidget(self._notify)
        gl.addWidget(self._track)

        grow = QHBoxLayout()
        grow.addWidget(_label("Daily screen-time goal (hours)", 10, color="#9E9E9E"))
        grow.addStretch()
        self._goal = QSpinBox()
        self._goal.setRange(1, 16)
        self._goal.setValue(int(self._settings.get("analytics", "daily_goal_hours", 8)))
        grow.addWidget(self._goal)
        gl.addLayout(grow)

        gl.addWidget(_label("Breaks", 13, True))
        self._forced = QCheckBox("Forced breaks (cannot skip)")
        self._sound = QCheckBox("Play break sound")
        self._forced.setChecked(bool(self._settings.get("break_timer", "forced_break", False)))
        self._sound.setChecked(bool(self._settings.get("break_timer", "sound_enabled", True)))
        gl.addWidget(self._forced)
        gl.addWidget(self._sound)

        wrow = QHBoxLayout()
        wrow.addWidget(_label("Work interval (minutes)", 10, color="#9E9E9E"))
        wrow.addStretch()
        self._work_min = QSpinBox()
        self._work_min.setRange(5, 90)
        self._work_min.setValue(int(self._settings.get("break_timer", "work_interval_minutes", 20)))
        wrow.addWidget(self._work_min)
        gl.addLayout(wrow)

        gl.addWidget(_label("Posture", 13, True))
        self._posture_on = QCheckBox("Posture reminders")
        self._posture_on.setChecked(bool(self._settings.get("posture", "enabled", True)))
        gl.addWidget(self._posture_on)
        prow = QHBoxLayout()
        prow.addWidget(_label("Interval (minutes)", 10, color="#9E9E9E"))
        prow.addStretch()
        self._posture_min = QSpinBox()
        self._posture_min.setRange(5, 120)
        self._posture_min.setValue(int(self._settings.get("posture", "interval_minutes", 30)))
        prow.addWidget(self._posture_min)
        gl.addLayout(prow)

        save = QPushButton("Save settings")
        save.setObjectName("primary")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self._save_general_settings)
        gl.addWidget(save, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(gen)

        path = QLabel(f"Database: {self._db.db_path()}")
        path.setStyleSheet("color: #6E6E6E; font-size: 10px;")
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(path)
        return page

    def _save_name(self) -> None:
        ok = self._db.update_display_name(self._set_name.text())
        if ok:
            self._user_chip.setText(self._set_name.text().strip())
            self._pin_status.setText("Name saved.")
            self._pin_status.setStyleSheet(f"color: {_GREEN};")

    def _save_pin(self) -> None:
        ok = self._db.change_pin(self._old_pin.text(), self._new_pin.text())
        if ok:
            self._pin_status.setText("PIN updated.")
            self._pin_status.setStyleSheet(f"color: {_GREEN};")
            self._old_pin.clear()
            self._new_pin.clear()
        else:
            self._pin_status.setText("Could not update PIN. Check the current PIN (4–6 digits).")
            self._pin_status.setStyleSheet(f"color: {_RED};")

    def _save_general_settings(self) -> None:
        s = self._settings
        s.set("app", "start_with_windows", self._start_win.isChecked())
        s.set("app", "show_notifications", self._notify.isChecked())
        s.set("analytics", "track_screen_time", self._track.isChecked())
        s.set("analytics", "daily_goal_hours", self._goal.value())
        s.set("break_timer", "forced_break", self._forced.isChecked())
        s.set("break_timer", "sound_enabled", self._sound.isChecked())
        s.set("break_timer", "work_interval_minutes", self._work_min.value())
        s.set("posture", "enabled", self._posture_on.isChecked())
        s.set("posture", "interval_minutes", self._posture_min.value())
        s.save()
        self._work_total = self._work_min.value() * 60
        self.settings_changed.emit()
        self._pin_status.setText("Settings saved.")
        self._pin_status.setStyleSheet(f"color: {_GREEN};")

    # ------------------------------------------------------------------
    # Optimistic overlay handlers
    # ------------------------------------------------------------------

    def _on_bl_toggled(self, checked: bool) -> None:
        self._set_checked_silent(self._tog_bl, checked)
        self._set_checked_silent(self._live_bl, checked)
        self.blue_light_toggled.emit(checked)
        self._settings.set("blue_light", "enabled", checked)
        self._schedule_persist()

    def _on_dim_toggled(self, checked: bool) -> None:
        self._set_checked_silent(self._tog_dim, checked)
        self._set_checked_silent(self._live_dim, checked)
        self.dim_toggled.emit(checked)
        self._settings.set("dim_engine", "enabled", checked)
        self._schedule_persist()

    def _on_focus_toggled(self, checked: bool) -> None:
        self._set_checked_silent(self._tog_focus, checked)
        self._set_checked_silent(self._focus_enable, checked)
        self.focus_toggled.emit(checked)
        self._settings.set("focus_mode", "enabled", checked)
        self._sync_focus_pill()
        self._schedule_persist()

    def _quick_toggle_focus(self) -> None:
        self._on_focus_toggled(not self._settings.get("focus_mode", "enabled", False))

    def _on_temp_preview(self, value: int) -> None:
        self._live_temp_lbl.setText(f"{value}K")
        opacity = self._live_op.value() / 100.0
        self.blue_light_preview.emit(value, opacity)
        self._settings.set("blue_light", "color_temperature", value)
        self._schedule_persist()

    def _on_op_preview(self, value: int) -> None:
        self._live_op_lbl.setText(f"{value}%")
        self.blue_light_preview.emit(self._live_temp.value(), value / 100.0)
        self._settings.set("blue_light", "opacity", value / 100.0)
        self._schedule_persist()

    def _on_dim_preview(self, value: int) -> None:
        self._live_dim_lbl.setText(f"{value}%")
        self.dim_preview.emit(value / 100.0)
        self._settings.set("dim_engine", "opacity", value / 100.0)
        self._schedule_persist()

    def _on_focus_preview(self, *_args) -> None:
        opacity = self._focus_op.value() / 100.0
        self._focus_op_lbl.setText(f"{self._focus_op.value()}%")
        gray = self._focus_gray.isChecked()
        self.focus_preview.emit(opacity, gray)
        self._settings.set("focus_mode", "dim_opacity", opacity)
        self._settings.set("focus_mode", "grayscale", gray)
        self._schedule_persist()

    def _schedule_persist(self) -> None:
        self._persist_timer.start(400)

    def _flush_settings(self) -> None:
        self._settings.save()

    def _sync_focus_pill(self) -> None:
        on = bool(self._settings.get("focus_mode", "enabled", False))
        self._focus_pill.setText("Focus  ·  On" if on else "Focus  ·  Off")

    @staticmethod
    def _set_checked_silent(box: QCheckBox, checked: bool) -> None:
        box.blockSignals(True)
        box.setChecked(checked)
        box.blockSignals(False)

    # ------------------------------------------------------------------
    # Live break progress (from AppController)
    # ------------------------------------------------------------------

    def set_work_total(self, seconds: int) -> None:
        self._work_total = max(1, seconds)

    def update_work_tick(self, seconds_remaining: int) -> None:
        total = max(1, self._work_total)
        remaining = max(0, seconds_remaining)
        elapsed = max(0, total - remaining)
        self._break_bar.setValue(int(elapsed / total * 1000))
        m, s = divmod(remaining, 60)
        if remaining <= 0:
            self._break_hint.setText("Break window — look 20 feet away.")
            self._break_bar.setStyleSheet("QProgressBar::chunk { background-color: #EF5350; }")
        elif remaining < 60:
            self._break_hint.setText(f"Almost there  ·  {s}s until your look-away.")
            self._break_bar.setStyleSheet("QProgressBar::chunk { background-color: #FFB74D; }")
        else:
            self._break_hint.setText(f"Next 20-20-20 break in {m:02d}:{s:02d}")
            self._break_bar.setStyleSheet("QProgressBar::chunk { background-color: #69F0AE; }")

    def on_break_started(self) -> None:
        self._break_hint.setText("Break in progress — 20 feet, 20 seconds. You’ve got this.")
        self._break_bar.setValue(1000)
        self._break_bar.setStyleSheet("QProgressBar::chunk { background-color: #82B1FF; }")

    def on_break_ended(self, completed: bool) -> None:
        if completed:
            self._break_hint.setText("Nice. Eyes reset. Back to the one window that matters.")
        else:
            self._break_hint.setText("Skipped — the next cue will come around again.")
        self._refresh_dashboard_stats()

    def _refresh_all(self) -> None:
        self.show_page("dashboard")
        self._refresh_dashboard_stats()
        self._render_profiles()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.hide()
        event.ignore()

"""
dashboard_window.py - Analytics dashboard for NeuroShield Eye.

Shows today's stats and a 7-day history chart. Uses pyqtgraph for
the bar chart. Dark-themed, modeless window that can be opened/closed
repeatedly without recreating the underlying data connections.
"""

from datetime import date
from typing import Optional

import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from utils.logger import get_logger

log = get_logger("dashboard_window")

# Configure pyqtgraph defaults
pg.setConfigOption("background", "#0d1117")
pg.setConfigOption("foreground", "#8b949e")


def _stat_card(title: str, value: str, unit: str = "", accent: str = "#58a6ff") -> QFrame:
    """Helper that builds a styled stat card widget."""
    card = QFrame()
    card.setFrameShape(QFrame.Shape.StyledPanel)
    card.setStyleSheet(f"""
        QFrame {{
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 10px;
        }}
    """)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(4)

    title_label = QLabel(title)
    title_label.setFont(QFont("Segoe UI", 9))
    title_label.setStyleSheet("color: #8b949e; border: none; background: transparent;")
    layout.addWidget(title_label)

    val_layout = QHBoxLayout()
    val_layout.setSpacing(4)
    val_label = QLabel(value)
    val_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
    val_label.setStyleSheet(f"color: {accent}; border: none; background: transparent;")
    val_layout.addWidget(val_label)

    if unit:
        unit_label = QLabel(unit)
        unit_label.setFont(QFont("Segoe UI", 11))
        unit_label.setStyleSheet("color: #8b949e; border: none; background: transparent;")
        unit_label.setAlignment(Qt.AlignmentFlag.AlignBottom)
        val_layout.addWidget(unit_label)
    val_layout.addStretch()
    layout.addLayout(val_layout)

    return card


class DashboardWindow(QMainWindow):
    """
    Analytics dashboard window.

    Shows today's screen time, breaks, posture alerts, and a 7-day
    bar chart. Auto-refreshes every 60 seconds when open.
    """

    def __init__(self, db) -> None:
        super().__init__()
        self._db = db
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(60_000)
        self._refresh_timer.timeout.connect(self.refresh)

        self._setup_window()
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowTitle("NeuroShield Eye — Dashboard")
        self.setMinimumSize(760, 560)
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0d1117;
                color: #e6edf3;
                font-family: 'Segoe UI';
            }
            QScrollBar:vertical {
                background: #161b22;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #30363d;
                border-radius: 4px;
            }
        """)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.setCentralWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(32, 28, 32, 28)
        main_layout.setSpacing(24)

        # --- Header ---
        header_layout = QHBoxLayout()
        title = QLabel("📊 Screen Health Dashboard")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #e6edf3;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.setFixedHeight(32)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 0 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #e6edf3;
            }
        """)
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)
        main_layout.addLayout(header_layout)

        # --- Today label ---
        self._date_label = QLabel()
        self._date_label.setFont(QFont("Segoe UI", 10))
        self._date_label.setStyleSheet("color: #8b949e;")
        main_layout.addWidget(self._date_label)

        # --- Today stat cards ---
        cards_grid = QGridLayout()
        cards_grid.setSpacing(12)
        self._card_screen_time = _stat_card("Screen Time Today", "0", "min", "#58a6ff")
        self._card_breaks_done = _stat_card("Breaks Completed", "0", "", "#3fb950")
        self._card_breaks_missed = _stat_card("Breaks Missed", "0", "", "#f85149")
        self._card_streak = _stat_card("Break Streak", "0", "days", "#f0883e")
        cards_grid.addWidget(self._card_screen_time, 0, 0)
        cards_grid.addWidget(self._card_breaks_done, 0, 1)
        cards_grid.addWidget(self._card_breaks_missed, 0, 2)
        cards_grid.addWidget(self._card_streak, 0, 3)
        main_layout.addLayout(cards_grid)

        # --- 7-day chart ---
        chart_label = QLabel("7-Day Break History")
        chart_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        chart_label.setStyleSheet("color: #e6edf3;")
        main_layout.addWidget(chart_label)

        self._chart_widget = pg.PlotWidget()
        self._chart_widget.setMinimumHeight(220)
        self._chart_widget.showGrid(y=True, alpha=0.3)
        self._chart_widget.getAxis("left").setLabel("Breaks Done")
        self._chart_widget.setMouseEnabled(x=False, y=False)
        self._chart_widget.setMenuEnabled(False)
        main_layout.addWidget(self._chart_widget)

        # --- Screen time chart ---
        time_chart_label = QLabel("7-Day Screen Time (minutes)")
        time_chart_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        time_chart_label.setStyleSheet("color: #e6edf3;")
        main_layout.addWidget(time_chart_label)

        self._time_chart_widget = pg.PlotWidget()
        self._time_chart_widget.setMinimumHeight(220)
        self._time_chart_widget.showGrid(y=True, alpha=0.3)
        self._time_chart_widget.getAxis("left").setLabel("Minutes")
        self._time_chart_widget.setMouseEnabled(x=False, y=False)
        self._time_chart_widget.setMenuEnabled(False)
        main_layout.addWidget(self._time_chart_widget)

        # --- All-time total ---
        self._alltime_label = QLabel()
        self._alltime_label.setFont(QFont("Segoe UI", 10))
        self._alltime_label.setStyleSheet("color: #8b949e;")
        main_layout.addWidget(self._alltime_label)
        main_layout.addStretch()

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Pull fresh data from the database and update all UI elements."""
        today_str = date.today().strftime("%A, %B %d %Y")
        self._date_label.setText(f"Today: {today_str}")

        # Today stats
        stats = self._db.get_today_stats()
        self._update_card(self._card_screen_time, str(stats.get("screen_minutes", 0)))
        self._update_card(self._card_breaks_done, str(stats.get("breaks_done", 0)))
        self._update_card(self._card_breaks_missed, str(stats.get("breaks_missed", 0)))

        streak = self._db.get_break_streak()
        self._update_card(self._card_streak, str(streak))

        all_time = self._db.get_all_time_total_hours()
        self._alltime_label.setText(f"Total tracked screen time: {all_time} hours")

        # Weekly chart
        weekly = self._db.get_weekly_stats()
        self._render_break_chart(weekly)
        self._render_time_chart(weekly)

        log.debug("Dashboard refreshed.")

    def _update_card(self, card: QFrame, value: str) -> None:
        """Find and update the value label inside a stat card."""
        for child in card.findChildren(QLabel):
            font = child.font()
            if font.pointSize() >= 20:
                child.setText(value)
                return

    def _render_break_chart(self, weekly: list[dict]) -> None:
        self._chart_widget.clear()
        if not weekly:
            return
        x = list(range(len(weekly)))
        y_done = [row.get("breaks_done", 0) for row in weekly]
        y_missed = [row.get("breaks_missed", 0) for row in weekly]

        bar_done = pg.BarGraphItem(x=x, height=y_done, width=0.35,
                                   brush=QColor("#3fb950"), pen=pg.mkPen(None))
        bar_missed = pg.BarGraphItem(x=[xi + 0.37 for xi in x], height=y_missed,
                                     width=0.35, brush=QColor("#f85149"), pen=pg.mkPen(None))
        self._chart_widget.addItem(bar_done)
        self._chart_widget.addItem(bar_missed)

        labels = [row.get("stat_date", "")[-5:] for row in weekly]
        axis = self._chart_widget.getAxis("bottom")
        axis.setTicks([list(zip(x, labels))])

    def _render_time_chart(self, weekly: list[dict]) -> None:
        self._time_chart_widget.clear()
        if not weekly:
            return
        x = list(range(len(weekly)))
        y = [row.get("screen_minutes", 0) for row in weekly]

        bars = pg.BarGraphItem(x=x, height=y, width=0.6,
                               brush=QColor("#58a6ff"), pen=pg.mkPen(None))
        self._time_chart_widget.addItem(bars)

        labels = [row.get("stat_date", "")[-5:] for row in weekly]
        axis = self._time_chart_widget.getAxis("bottom")
        axis.setTicks([list(zip(x, labels))])

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()
        self._refresh_timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        self._refresh_timer.stop()

    def closeEvent(self, event) -> None:  # noqa: N802
        """Hide instead of destroy so the window can be reopened."""
        self._refresh_timer.stop()
        self.hide()
        event.ignore()

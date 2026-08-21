# NeuroShield Eye Pro 👁️

> **ADHD Edition — a low-distraction, offline CareUEyes-style desktop app for Windows**

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python)](https://python.org)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green)](https://pypi.org/project/PyQt6/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightblue?logo=windows)](https://www.microsoft.com/windows)
[![SQLite](https://img.shields.io/badge/Database-SQLite-orange)](https://sqlite.org)

NeuroShield Eye Pro is a full-stack, privacy-first Windows desktop app for ADHD users and anyone who lives on a screen. A sidebar dashboard maps the whole app (so you never hunt through menus), Focus Mode visually anchors the active window, and protection profiles remember a setup so you set it once and stop fiddling.

Everything is local. No accounts in the cloud, no telemetry.

---

## Why this edition

| Need | What the app does |
|------|-------------------|
| **Visual anchoring** | Focus Mode dims everything except the window you are using. |
| **Structure** | Left sidebar: Dashboard, Eye Protection, Focus Mode, Analytics, Settings. |
| **Set it and forget it** | Named protection profiles (`Late Night Coding`, `Reading`, `Outdoor`, `Gaming Mode`, `Deep Focus`). |
| **Gamified 20-20-20** | Progress bar + color cues until the next look-away. |
| **Private** | Local PIN (PBKDF2 in SQLite). Settings never leave this PC. |

---

## Features

- **Local PIN profile** — first-run setup, lock from the sidebar, hashed PIN in `neuroshield.db`
- **Blue light overlay** — click-through warm tint, live temperature / strength sliders (optimistic: overlay moves before SQLite/JSON confirm)
- **Software dim** — black click-through overlay below hardware minimum
- **Focus Mode** — hole-punched dimmer around the foreground window
- **Protection profiles CRUD** — create, apply, edit, delete; empty state if you delete them all
- **20-20-20 breaks** — fullscreen cue, optional forced break, tray “break now”
- **Analytics** — 7-day screen time, eye-strain, break charts (demo week seeded on first run)
- **System tray** — keep running with the dashboard closed

---

## Architecture

Flat folder. One Python module per concern. No nested packages.

```
NeuroShield-Eye/
├── main.py                  # AppController — wires auth, UI, engines
├── auth_window.py           # Local PIN setup / unlock
├── dashboard_window.py      # Sidebar shell + CRUD + charts
├── database_manager.py      # SQLite: users, profiles, logs
├── blue_light_overlay.py    # Warm click-through tint
├── dim_engine.py            # Black click-through tint
├── focus_mode.py            # Visual-anchor dimmer
├── break_timer.py           # 20-20-20 engine
├── posture_reminder.py
├── tray_manager.py
├── settings_manager.py
├── settings_panel.py        # Legacy tabbed panel (still importable)
├── logger.py
├── default_config.json
└── neuroshield.db           # created at runtime under %APPDATA%
```

Imports stay flat: `import database_manager`, `import dim_engine`, …

Runtime data:

| File | Location |
|------|----------|
| Database | `%APPDATA%\NeuroShieldEye\neuroshield.db` |
| User config | `%APPDATA%\NeuroShieldEye\user_config.json` |
| Logs | `%APPDATA%\NeuroShieldEye\logs\neuroshield.log` |

---

## Requirements

- Windows 10/11 (64-bit) for overlays, tray, and Focus Mode hole-punching
- Python 3.10+ (3.12 recommended)
- pip

---

## Install & run

```bash
git clone https://github.com/avinabmaharjan/NeuroShield-Eye.git
cd NeuroShield-Eye
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python generate_assets.py
python main.py
```

First launch: create a display name + 4–6 digit PIN. The dashboard opens after unlock; the tray icon stays available.

---

## Build executable (PyInstaller)

```bash
pip install pyinstaller
python generate_assets.py
pyinstaller NeuroShieldEye.spec
# Output: dist/NeuroShieldEye.exe
```

---

## Tests

```bash
pip install pytest
pytest test_database_manager.py -q
```

---

## Privacy

100% offline. The PIN is stored as PBKDF2-HMAC-SHA256 (120k rounds) plus a random salt. Protection profiles and analytics never leave the SQLite file on this machine.

---

## License

MIT — see [LICENSE](LICENSE) if present in this repository.

*Built for people who stare at screens too long, and whose attention has somewhere better to be.*

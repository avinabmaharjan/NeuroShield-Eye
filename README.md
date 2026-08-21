# NeuroShield Eye

**Intelligent eye protection and screen health management for Windows 11**

NeuroShield Eye is a small Windows desktop app I built because spending long hours in front of a screen became too easy to ignore.

It started from a simple problem: I wanted something that could remind me to take breaks, make long screen sessions less tiring, and help me build better computer habits without constantly sending my data somewhere.

So instead of another web service or account-based health app, NeuroShield Eye is designed to stay on the computer and do its job quietly.

It runs from the system tray and handles things like blue-light filtering, screen dimming, break reminders, focus mode, posture reminders, and basic screen-time tracking. Everything is kept locally.

## What it does

* Blue-light filter with adjustable warmth and opacity
* 20-20-20 break reminders, plus custom intervals
* Fullscreen break mode with countdown and optional forced breaks
* Software dimming below the normal Windows brightness limit
* Focus mode that dims inactive windows
* Optional grayscale mode
* Screen-time and break tracking
* Posture reminders
* Local dashboard for basic statistics
* System tray controls
* Settings saved locally
* Optional Windows startup

There is no account system, cloud dashboard, or telemetry.

## Why I made it

This project is partly about eye health, but it is also about attention and routine.

When you're working, studying, coding, or gaming for hours, it is surprisingly easy to keep going without noticing how long you've been sitting there. I wanted the computer itself to become a reminder instead of another source of distraction.

I also wanted to experiment with building a practical desktop application around privacy, accessibility, and personal data ownership.

## How it is built

NeuroShield Eye is written in Python using PyQt6.

The application is split into small modules so features can be changed without turning the whole project into one large file. The main controller connects the different components through Qt signals.

The main parts are:

* `tray_manager.py` handles the system tray
* `blue_light_overlay.py` handles the screen filter
* `break_timer.py` handles break scheduling
* `dim_engine.py` handles software dimming
* `focus_mode.py` handles focus behaviour
* `posture_reminder.py` handles reminders
* `dashboard_window.py` handles the interface and statistics
* `database_manager.py` handles local SQLite data
* `settings_manager.py` handles configuration
* `logger.py` handles application logging

## Requirements

* Windows 11, 64-bit
* Python 3.12+
* pip

## Installation

```bash
git clone https://github.com/avinabmaharjan/NeuroShield-Eye.git
cd NeuroShield-Eye

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
python generate_assets.py
python main.py
```

## Build

The project can also be packaged into a standalone Windows executable with PyInstaller.

```bash
pip install pyinstaller

pyinstaller --noconfirm --onefile --windowed ^
  --icon=assets/tray_icon.ico ^
  --add-data "assets;assets" ^
  --add-data "config;config" ^
  --name "NeuroShieldEye" ^
  src/main.py
```

The executable will be placed in:

```text
dist/NeuroShieldEye.exe
```

## Privacy

NeuroShield Eye is designed to work completely offline.

There are no accounts, analytics services, or telemetry. Screen-health data is stored locally in SQLite:

```text
%APPDATA%\NeuroShieldEye\data.db
```

The idea is simple: your screen habits should belong to you.

## Project structure

```text
NeuroShield-Eye/
├── config/
├── assets/
├── src/
│   ├── tray/
│   ├── overlay/
│   ├── break_system/
│   ├── brightness/
│   ├── focus/
│   ├── posture/
│   ├── dashboard/
│   ├── database/
│   ├── settings/
│   └── utils/
├── requirements.txt
├── README.md
└── LICENSE
```

## What's next

Some things I would like to explore later:

* Ambient-light based adjustments
* Better break-screen customization
* CSV/PDF export
* Multiple profiles for work, gaming, and night use
* Better Windows notification integration
* Possible Linux and macOS support

This is still a work in progress, but the goal is intentionally simple: make spending long hours at a computer a little healthier without making the software itself another distraction.

## License

MIT License.

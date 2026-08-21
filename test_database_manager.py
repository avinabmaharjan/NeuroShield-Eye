"""SQLite / auth / profile CRUD tests — no GUI required."""

from pathlib import Path

from database_manager import DatabaseManager


def _db(tmp_path: Path) -> DatabaseManager:
    return DatabaseManager(tmp_path / "neuroshield.db")


def test_seed_creates_profiles_and_week(tmp_path):
    db = _db(tmp_path)
    profiles = db.list_profiles()
    assert len(profiles) >= 4
    names = {p["name"] for p in profiles}
    assert "Late Night Coding" in names
    assert "Gaming Mode" in names
    week = db.get_weekly_stats()
    assert len(week) == 7
    assert sum(r["screen_minutes"] for r in week) > 0
    assert any(r["eye_strain_score"] > 0 for r in week)


def test_auth_pin_roundtrip(tmp_path):
    db = _db(tmp_path)
    assert db.has_user() is False
    assert db.create_user("Alex", "2468") is True
    assert db.has_user() is True
    assert db.create_user("Other", "1111") is False  # one local profile
    assert db.verify_pin("2468") is True
    assert db.verify_pin("0000") is False
    assert db.change_pin("2468", "9999") is True
    assert db.verify_pin("9999") is True
    assert db.verify_pin("2468") is False
    user = db.get_user()
    assert user["display_name"] == "Alex"
    assert db.update_display_name("Sam")
    assert db.get_user()["display_name"] == "Sam"


def test_profile_crud(tmp_path):
    db = _db(tmp_path)
    new_id = db.create_profile({
        "name": "Custom Calm",
        "description": "Low stimulation",
        "blue_light_enabled": True,
        "color_temperature": 2500,
        "blue_light_opacity": 0.4,
        "dim_enabled": True,
        "dim_opacity": 0.2,
        "focus_enabled": True,
    })
    assert new_id
    fetched = db.get_profile(new_id)
    assert fetched["name"] == "Custom Calm"
    assert fetched["focus_enabled"] == 1
    db.update_profile(new_id, {
        "name": "Custom Calm v2",
        "description": "Updated",
        "blue_light_enabled": False,
        "color_temperature": 5000,
        "blue_light_opacity": 0.1,
        "dim_enabled": False,
        "dim_opacity": 0.0,
        "focus_enabled": False,
    })
    fetched = db.get_profile(new_id)
    assert fetched["name"] == "Custom Calm v2"
    assert fetched["blue_light_enabled"] == 0
    db.set_active_profile(new_id)
    assert db.get_active_profile_id() == new_id
    assert db.delete_profile(new_id) is True
    assert db.get_profile(new_id) is None


def test_break_and_stats(tmp_path):
    db = _db(tmp_path)
    bid = db.record_break_start("20-20-20")
    assert bid > 0
    db.record_break_end(bid, True)
    today = db.get_today_stats()
    assert today["breaks_done"] >= 1
    db.add_screen_minutes(15)
    today = db.get_today_stats()
    assert today["screen_minutes"] >= 15

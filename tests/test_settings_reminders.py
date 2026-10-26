import pytest

from meeting_companion.config.settings import MODES, Settings
from meeting_companion.services.reminders import Reminders


def test_settings_round_trip(tmp_path):
    settings = Settings(mode="Both", autosave=True)
    path = tmp_path / "settings.json"
    settings.save(path)
    assert Settings.load(path) == settings
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.parametrize("settings", [Settings(mode="Wrong"), Settings(theme="bad"),
                                     Settings(reminder_minutes=0), Settings(cooldown_minutes=1500),
                                     Settings(autosave="yes")])
def test_settings_reject_invalid_values(settings):
    with pytest.raises(ValueError):
        settings.validate()


def test_settings_defaults_require_explicit_capture_and_reminder_opt_in():
    settings = Settings()
    assert settings.mode == "Both"
    assert not settings.startup and not settings.reminders and not settings.autosave
    assert not settings.setup_complete


def test_malformed_settings_are_not_silently_overwritten(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("broken", encoding="utf-8")
    with pytest.raises(ValueError):
        Settings.load(path)
    assert path.read_text() == "broken"


def test_reminder_interval_cooldown_and_active_suppression():
    now = [0.0]
    settings = Settings(reminders=True, reminder_minutes=5, cooldown_minutes=10)
    reminders = Reminders(settings, clock=lambda: now[0])
    now[0] = 301
    assert reminders.due(False)
    now[0] = 601
    assert not reminders.due(False)
    now[0] = 1202
    assert not reminders.due(True)
    now[0] = 1450
    assert not reminders.due(False)
    now[0] = 1803
    assert reminders.due(False)


def test_disabled_reminder_never_notifies():
    now = [0]
    reminders = Reminders(Settings(), lambda: now[0])
    now[0] = 1e9
    assert not reminders.due(False)

from __future__ import annotations

import time


class Reminders:
    """Local opt-in timer. It never infers meeting attendance or starts capture."""

    def __init__(self, settings, clock=time.monotonic):
        self.settings = settings
        self.clock = clock
        self.last_activity = clock()
        self.last_reminder = float("-inf")

    def activity(self):
        self.last_activity = self.clock()

    def due(self, active: bool) -> bool:
        now = self.clock()
        if active:
            self.last_activity = now
            return False
        if not self.settings.reminders:
            return False
        if (now - self.last_activity >= self.settings.reminder_minutes * 60
                and now - self.last_reminder >= self.settings.cooldown_minutes * 60):
            self.last_reminder = now
            return True
        return False

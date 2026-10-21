"""Deadline reminders as Windows notifications (G156).

The notification is drawn by Windows on this device; nothing is sent anywhere.
The service is opt-in: with ``[reminders] enabled = false`` nothing is shown
at all, and the same reminder is never shown twice on the same day.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Callable

from PySide6.QtWidgets import QApplication, QStyle, QSystemTrayIcon

from scholarpath.reminders import Reminder, due_reminders
from scholarpath.storage import Database

logger = logging.getLogger("scholarpath.ui.reminders")

#: The tray icon is kept alive: a notification that is shown by a temporary
#: object would disappear with it.
_TRAY: QSystemTrayIcon | None = None


def show_notification(title: str, message: str, duration_ms: int = 8000) -> bool:
    """Show a local Windows notification. False when there is no tray."""
    global _TRAY
    app = QApplication.instance()
    if app is None:
        logger.info("reminder (no application yet): %s - %s", title, message)
        return False
    try:
        if _TRAY is None:
            style = app.style()
            icon = style.standardIcon(QStyle.SP_MessageBoxInformation)
            _TRAY = QSystemTrayIcon(icon)
            _TRAY.setToolTip("ScholarPath AI")
        _TRAY.show()
        _TRAY.showMessage(title, message, QSystemTrayIcon.Information, duration_ms)
    except Exception:  # noqa: BLE001 - a missing tray must not break the app
        logger.exception("the reminder could not be shown")
        return False
    return True


class ReminderService:
    """Shows the reminders that are due, once each."""

    def __init__(
        self,
        database: Database,
        enabled: bool = True,
        notify: Callable[[str, str], bool] = show_notification,
    ) -> None:
        self._database = database
        self._enabled = enabled
        self._notify = notify

    @property
    def enabled(self) -> bool:
        return self._enabled

    def due(self, today: date | None = None) -> list[Reminder]:
        """The reminders that are due today, without showing them."""
        if not self._enabled:
            return []
        records = list(self._database.catalog_records())
        saved = self._database.saved_opportunity_ids()
        return due_reminders(records, today, saved)

    def show_due(self, today: date | None = None) -> list[Reminder]:
        """Show the reminders that are due, and remember that they were shown."""
        if not self._enabled:
            return []
        day = (today or date.today()).isoformat()
        shown: list[Reminder] = []
        for reminder in self.due(today):
            if not self._database.reminder_shown(
                reminder.scholarship_id, reminder.days_before, day
            ):
                continue  # already shown today
            self._notify("ScholarPath - deadline reminder", reminder.message)
            shown.append(reminder)
        return shown

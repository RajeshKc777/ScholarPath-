"""My Profile page: a local-first form for academic facts (Milestone 3).

Everything lives in the local SQLite database; nothing is sent anywhere. Every
value is optional and clearly labelled as "not set" until the user fills it -
this page never invents a fact.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from scholarpath.profiles import Profile
from scholarpath.storage import Database

logger = logging.getLogger("scholarpath.ui.profile")

DEGREE_LABELS = {
    "": "Not set",
    "bachelor": "Bachelor graduate",
    "master": "Master applicant / graduate",
    "phd": "PhD scholar",
    "postdoc": "Postdoc",
    "other": "Other",
}
GPA_SCALES = ("", "4.0", "5.0", "10", "percentage", "unknown")
SCALE_LABELS = {
    "": "Not set",
    "4.0": "0 - 4.0",
    "5.0": "0 - 5.0",
    "10": "0 - 10",
    "percentage": "Percentage (0 - 100)",
    "unknown": "Other scale",
}


def _scale_of(value: str) -> str:
    """Map stored scale to the combo value."""
    return value.strip() if value.strip() in GPA_SCALES else ""


class ProfilePage(QWidget):
    def __init__(
        self,
        database: Database,
        on_saved: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database = database
        self._on_saved = on_saved
        self._profile = Profile()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(14)

        header = QVBoxLayout()
        header.setSpacing(3)
        title = QLabel("Your academic profile", self)
        title.setObjectName("PageTitle2")
        lead = QLabel(
            "Local-only. This is what the app (later: research and eligibility "
            "checks) will work from. You fill it yourself or confirm extracted "
            "values one by one - nothing is saved automatically.",
            self,
        )
        lead.setObjectName("PageLead")
        lead.setWordWrap(True)
        header.addWidget(title)
        header.addWidget(lead)
        outer.addLayout(header)

        card = QFrame(self)
        card.setObjectName("PanelCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(18, 18, 18, 18)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)

        self._name = self._field("Student name", grid, 0, 0)
        self._nationality = self._field("Nationality", grid, 0, 2)
        self._degree = self._combo(
            "Degree level", DEGREE_LABELS, grid, 1, 0, editable=True)
        self._discipline = self._field("Discipline", grid, 1, 2)
        self._institution = self._field("Institution", grid, 2, 0)
        self._year = self._field("Graduation year", grid, 2, 2)
        self._gpa = self._field("GPA", grid, 3, 0)
        self._scale = self._combo("GPA scale", SCALE_LABELS, grid, 3, 2)
        self._ielts = self._field("IELTS overall", grid, 4, 0)
        self._toefl = self._field("TOEFL", grid, 4, 2)
        self._countries = self._field("Preferred countries", grid, 5, 0)
        self._funding = self._field("Funding needed", grid, 5, 2)

        outer.addWidget(card, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        self._saved_label = QLabel("", self)
        self._saved_label.setObjectName("Hint")
        row.addWidget(self._saved_label)
        clear = QPushButton("Clear profile", self)
        clear.setObjectName("GhostButton")
        clear.clicked.connect(self._on_clear)
        row.addWidget(clear)
        save = QPushButton("Save profile", self)
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self._on_save)
        row.addWidget(save)
        outer.addLayout(row)
        self._load()

    # -- builders ----------------------------------------------------------
    def _field(self, label: str, grid: QGridLayout, row: int, column: int) -> QLineEdit:
        holder = QWidget(self)
        box = QVBoxLayout(holder)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(3)
        caption = QLabel(label, holder)
        caption.setObjectName("FieldLabel")
        edit = QLineEdit(holder)
        edit.setObjectName("PField")
        edit.setPlaceholderText("Not set")
        box.addWidget(caption)
        box.addWidget(edit)
        grid.addWidget(holder, row, column)
        return edit

    def _combo(
        self,
        label: str,
        options: dict[str, str],
        grid: QGridLayout,
        row: int,
        column: int,
        editable: bool = False,
    ) -> QComboBox:
        holder = QWidget(self)
        box = QVBoxLayout(holder)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(3)
        caption = QLabel(label, holder)
        caption.setObjectName("FieldLabel")
        combo = QComboBox(holder)
        combo.setObjectName("PCombo")
        for key, text in options.items():
            combo.addItem(text, key)
        if editable:
            # Free text is valid here (e.g. "Bachelor of Science" from a
            # transcript); keep it visible and stop it being wiped on save.
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.NoInsert)
            combo.lineEdit().setPlaceholderText("e.g. Bachelor of Science")
        box.addWidget(caption)
        box.addWidget(combo)
        grid.addWidget(holder, row, column)
        return combo

    # -- data ----------------------------------------------------------
    def _load(self) -> None:
        record = self._database.load_profile()
        payload = record["data"] if record else {}
        self._profile, dropped = Profile.from_payload(payload)
        self._name.setText(self._profile.student_name)
        self._nationality.setText(self._profile.nationality)
        self._discipline.setText(self._profile.discipline)
        self._institution.setText(self._profile.institution)
        self._year.setText(self._profile.graduation_year)
        self._gpa.setText(self._profile.gpa)
        self._degree.setCurrentIndex(self._degree.findData(self._profile.degree_level))
        if self._degree.currentIndex() < 0:
            self._degree.setEditText(self._profile.degree_level)
        self._scale.setCurrentIndex(self._scale.findData(_scale_of(self._profile.gpa_scale)))
        self._ielts.setText(self._profile.ielts)
        self._toefl.setText(self._profile.toefl)
        self._countries.setText(self._profile.preferred_countries)
        self._funding.setText(self._profile.funding_need)

    def refresh(self) -> None:
        """Reload from the database (e.g. after document confirmations)."""
        self._load()

    def profile(self) -> Profile:
        return self._profile

    def _apply_form_to_profile(self) -> Profile:
        """Build a fresh Profile from the form; the form is the source of truth."""
        # The degree combo is editable: a known choice stores its key, a typed
        # title (e.g. "Bachelor of Science") is kept verbatim.
        degree_text = self._degree.currentText().strip()
        degree_key = ""
        for index in range(self._degree.count()):
            if self._degree.itemText(index) == degree_text:
                degree_key = self._degree.itemData(index) or ""
                break
        if not degree_key and degree_text and degree_text != DEGREE_LABELS[""]:
            degree_key = degree_text
        scale_key = self._scale.currentData(Qt.UserRole) or ""
        return Profile(
            student_name=self._name.text().strip(),
            nationality=self._nationality.text().strip(),
            degree_level=degree_key,
            discipline=self._discipline.text().strip(),
            institution=self._institution.text().strip(),
            graduation_year=self._year.text().strip(),
            gpa=self._gpa.text().strip(),
            gpa_scale=scale_key,
            ielts=self._ielts.text().strip(),
            toefl=self._toefl.text().strip(),
            preferred_countries=self._countries.text().strip(),
            funding_need=self._funding.text().strip(),
            updated_at=self._profile.updated_at,
        )

    def _on_save(self) -> None:
        """Save the form and say, plainly, that it happened.

        A save that fails, or a side panel that does not refresh, must never
        look like a save that worked (G137).
        """
        profile = self._apply_form_to_profile()
        try:
            self._database.save_profile(profile.as_payload())
        except Exception as exc:  # noqa: BLE001 - the student must see this
            logger.exception("profile save failed")
            self._saved_label.setText(
                f"The profile could not be saved: {exc}. Nothing was changed."
            )
            return
        self._profile = profile
        stamp = time.strftime("%H:%M:%S")
        self._saved_label.setText(
            f"Saved locally \u2014 {profile.completion()}% complete (saved at {stamp})."
        )
        logger.info("profile saved locally, %d%% complete", profile.completion())
        if self._on_saved:
            try:
                self._on_saved()
            except Exception:  # noqa: BLE001 - the save itself already worked
                logger.exception("the views could not be refreshed after saving")
                self._saved_label.setText(
                    f"Saved locally \u2014 {profile.completion()}% complete (saved at "
                    f"{stamp}), but the side panel could not be refreshed."
                )

    def _on_clear(self) -> None:
        self._database.clear_profile()
        self._load()
        self._saved_label.setText("Profile cleared.")
        if self._on_saved:
            self._on_saved()

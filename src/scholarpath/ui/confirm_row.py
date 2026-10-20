"""Shared confirmation row: checkbox, editable value, verification marker.

Used by the documents page and the scholarship research page. The value is
always editable; the marker shows where it came from; only rows the user
ticks are written anywhere.
"""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QWidget


class ConfirmRow(QFrame):
    """One proposed value: checkbox + editable value + verification marker."""

    def __init__(
        self,
        label: str,
        value: str,
        verified: bool,
        reason: str = "",
        source_noun: str = "document",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DocCard")
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)

        self.check = QCheckBox(self)
        self.check.setChecked(verified)
        self.check.setToolTip(
            "Checked values are saved when you press the Apply/Save button."
        )
        row.addWidget(self.check)

        label_widget = QLabel(label, self)
        label_widget.setMinimumWidth(150)
        row.addWidget(label_widget)

        self.edit = QLineEdit(value, self)
        self.edit.setObjectName("PField")
        row.addWidget(self.edit, 1)

        if verified:
            marker = QLabel(f"\u2713 found in {source_noun}", self)
            marker.setObjectName("VerifyOK")
            marker.setToolTip(reason or "This value was copied from the source text.")
        else:
            marker = QLabel(f"? not found in {source_noun}", self)
            marker.setObjectName("VerifyWarn")
            marker.setToolTip(
                reason
                or "Proposed by the model, but it does not appear word-for-word in "
                "the source. Check it yourself before saving."
            )
        row.addWidget(marker)

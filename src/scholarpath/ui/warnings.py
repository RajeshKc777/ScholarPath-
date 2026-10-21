"""Warning signs on a card (G158).

One widget, used by every card that shows a record: the Saved list, the
Eligibility card and the Discover result. It says what the signs are and why
each one is there - and it never hides, changes or removes a record.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from scholarpath.scam_flags import WarningSign, evaluate_signs, signs_summary


class WarningSignsPanel(QWidget):
    """The warning signs of a record, with the reason for each one."""

    def __init__(
        self,
        record: dict | None = None,
        signs: list[WarningSign] | None = None,
        trusted_domains=(),
        parent: QWidget | None = None,
        expandable: bool = True,
    ) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)

        if signs is None:
            record = record or {}
            signs = evaluate_signs(
                record,
                page_text=str(record.get("page_text") or ""),
                trusted_domains=trusted_domains,
            )
        self.signs = signs
        if not signs:
            return

        summary = QLabel(signs_summary(signs), self)
        summary.setObjectName("StateWhat")
        summary.setWordWrap(True)
        column.addWidget(summary)

        if not expandable:
            for sign in signs:
                column.addWidget(self._sign_widget(sign, self))
            return

        toggle = QPushButton("Why this record?", self)
        toggle.setObjectName("LinkButton")
        toggle.setCursor(Qt.PointingHandCursor)
        column.addWidget(toggle)

        panel = QWidget(self)
        inner = QVBoxLayout(panel)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(4)
        for sign in signs:
            inner.addWidget(self._sign_widget(sign, panel))
        note = QLabel(
            "A warning sign is a fact about the page, not a verdict about it. "
            "Nothing is hidden or removed - open the page and decide.",
            panel,
        )
        note.setObjectName("DocMeta")
        note.setWordWrap(True)
        inner.addWidget(note)
        inner.addStretch(1)
        panel.setVisible(False)
        column.addWidget(panel)
        toggle.clicked.connect(lambda: panel.setVisible(not panel.isVisible()))

    @staticmethod
    def _sign_widget(sign: WarningSign, parent: QWidget) -> QWidget:
        holder = QWidget(parent)
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(1)
        headline = QLabel(sign.headline, holder)
        headline.setObjectName("StateWhat")
        headline.setWordWrap(True)
        column.addWidget(headline)
        detail = QLabel(sign.detail, holder)
        detail.setObjectName("DocMeta")
        detail.setWordWrap(True)
        column.addWidget(detail)
        if sign.evidence:
            evidence = QLabel(f"the page says: {sign.evidence}", holder)
            evidence.setObjectName("DocMeta")
            evidence.setWordWrap(True)
            evidence.setAlignment(Qt.AlignLeft)
            column.addWidget(evidence)
        return holder

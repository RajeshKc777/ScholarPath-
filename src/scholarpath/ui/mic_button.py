"""Animated microphone button with a listening ripple (G125).

Painted with QPainter - no image assets, no new dependency. While listening,
two soft orange rings expand from the button and fade out (a 1.4 s loop), the
button core fills with the accent colour and the glyph turns white. Outside
that state it is a quiet ghost button with a hover tint.

The widget stays enabled while listening, so a second click can stop the
capture (the UI wires `clicked` to the voice toggle).
"""

from __future__ import annotations

import time

from PySide6.QtCore import QPointF, QRect, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from scholarpath.ui import theme

MIC_GLYPH = "\uE720"
RIPPLE_SECONDS = 1.4
FRAME_MS = 16  # ~60 fps while listening; the timer stops otherwise


def ripple_rings(phase: float) -> list[tuple[float, float]]:
    """(radius fraction, opacity) for each ring at a 0..1 loop phase.

    Fraction runs from 0.55 (just outside the core) to 1.0 (widget edge);
    opacity fades from 1 to 0 so the ring dissolves as it grows.
    """
    rings: list[tuple[float, float]] = []
    for offset in (0.0, 0.5):
        t = (phase + offset) % 1.0
        rings.append((0.55 + 0.45 * t, 1.0 - t))
    return rings


class MicButton(QWidget):
    """Round mic button; `set_listening(True)` starts the ripple animation."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None, diameter: int = 54) -> None:
        super().__init__(parent)
        self.setFixedSize(diameter, diameter)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)  # typing must never lose focus to it
        self.setAccessibleName("Voice input")
        self._listening = False
        self._hover = False
        self._pressed = False
        self._started = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self.update)

    # -- state ---------------------------------------------------------------
    def is_listening(self) -> bool:
        return self._listening

    def set_listening(self, listening: bool) -> None:
        if listening == self._listening:
            return
        self._listening = listening
        if listening:
            self._started = time.monotonic()
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    # -- events --------------------------------------------------------------
    def enterEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._hover = False
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        was_pressed = self._pressed
        self._pressed = False
        self.update()
        if (
            was_pressed
            and event.button() == Qt.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    # -- painting ------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        palette = theme.PALETTE
        outer = min(self.width(), self.height()) / 2.0 - 1.0
        center = QPointF(self.width() / 2.0, self.height() / 2.0)

        if self._listening:
            phase = ((time.monotonic() - self._started) % RIPPLE_SECONDS) / RIPPLE_SECONDS
            accent = QColor(palette["orange"])
            for radius_fraction, opacity in ripple_rings(phase):
                radius = outer * radius_fraction
                ring_color = QColor(accent)
                ring_color.setAlphaF(0.6 * opacity)
                painter.setPen(QPen(ring_color, 2.2))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(center, radius, radius)
            painter.setPen(Qt.NoPen)
            painter.setBrush(accent)
            painter.drawEllipse(center, outer * 0.62, outer * 0.62)
            glyph_color = QColor("#FFFFFF")
        else:
            if self._hover:
                painter.setPen(Qt.NoPen)
                fill = QColor(palette["border"])
                fill.setAlphaF(0.55 if not self._pressed else 0.9)
                painter.setBrush(fill)
                painter.drawEllipse(center, outer * 0.62, outer * 0.62)
            glyph_color = QColor(palette["text_secondary"])

        font = QFont("Segoe MDL2 Assets")
        font.setPixelSize(16)
        painter.setFont(font)
        painter.setPen(glyph_color)
        painter.drawText(
            QRectF(QRect(0, 0, self.width(), self.height())),
            Qt.AlignCenter,
            MIC_GLYPH,
        )
        painter.end()

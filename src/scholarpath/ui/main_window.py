"""Main window: light dashboard shell for the Milestone 1 chat loop.

Layout follows the user-supplied dashboard reference: navy sidebar, top bar,
gradient welcome card, quick-action tiles, conversation column, academic
profile panel. Every value shown is real application state - the profile and
catalog values come from the local database, and the capability rows follow
the config.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from datetime import timedelta

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QLinearGradient,
    QPainter,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from scholarpath.chat_profile import merge_selected
from scholarpath.config import AppConfig, config_path
from scholarpath.profiles import Profile
from scholarpath.prose import humanize_reply
from scholarpath.recheck import RecheckStore
from scholarpath.storage import Database, database_path
from scholarpath.ui import theme
from scholarpath.ui.chat_controller import ChatController, Turn
from scholarpath.ui.mic_button import MicButton
from scholarpath.ui.profile_page import DEGREE_LABELS
from scholarpath.ui.profile_suggestion import ProfileSuggestionCard, _ProfileScanWorker
from scholarpath.tts import Speaker, engine_label, to_speech
from scholarpath.voice import availability, cancel_active, listen_once

logger = logging.getLogger("scholarpath.ui")

GLYPH_EDUCATION = "\uE7BE"
GLYPH_CHAT = "\uE8BD"
GLYPH_PERSON = "\uE77B"
GLYPH_STAR = "\uE734"
GLYPH_DOCUMENT = "\uE8A5"
GLYPH_SETTING = "\uE713"
GLYPH_SEND = "\uE724"
GLYPH_ATTACH = "\uE723"
GLYPH_MIC = "\uE720"
GLYPH_GLOBE = "\uE774"
GLYPH_SEARCH = "\uE721"

# How close to the bottom still counts as "following the conversation".
SCROLL_STICK_THRESHOLD = 12


def should_stick_to_bottom(
    maximum: int, value: int, threshold: int = SCROLL_STICK_THRESHOLD
) -> bool:
    """True when the scroll position is close enough to the bottom.

    The chat follows new messages while the student is at the bottom, and
    stops yanking the view when they scroll up to read earlier turns.
    """
    return (maximum - value) <= threshold
GLYPH_CHECK = "\uE73E"

ACTION_TILES = (
    ("Find Scholarships", "Search the verified catalog", "M4", GLYPH_STAR, "#FFF1E8", "#FF4500"),
    ("Check Eligibility", "Rule-based, no gaps", "M5", GLYPH_CHECK, "#EAF9F0", "#10B981"),
    ("Explore Countries", "Search the catalog", "M6", GLYPH_GLOBE, "#EAF2FF", "#3B82F6"),
    ("Upload Documents", "Marksheets, IDs", "M3", GLYPH_DOCUMENT, "#F3EEFF", "#8B5CF6"),
)


def icon_font(size: int) -> QFont:
    font = QFont("Segoe MDL2 Assets")
    font.setPixelSize(size)
    return font


def glyph_label(glyph: str, size: int, color: str, parent: QWidget | None = None) -> QLabel:
    label = QLabel(glyph, parent)
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet(
        f"color: {color}; background: transparent; "
        f"font-family: 'Segoe MDL2 Assets'; font-size: {size}px;"
    )
    return label


class FlowLayout(QLayout):
    """Left-to-right layout that wraps onto new lines when width runs out."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 10) -> None:
        super().__init__(parent)
        self._items: list = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:  # noqa: N802 - Qt API
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802 - Qt API
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):  # noqa: N802 - Qt API
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):  # noqa: N802 - Qt API
        return Qt.Orientations(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt API
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt API
        return self._layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802 - Qt API
        super().setGeometry(rect)
        self._layout(rect, apply=True)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802 - Qt API
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _layout(self, rect: QRect, apply: bool) -> int:
        x, y, line_height = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()


class LogoMark(QWidget):
    """Rounded gradient tile with a graduation cap - the brand mark."""

    def __init__(self, size: int = 38, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, QColor(theme.PALETTE["blue"]))
        gradient.setColorAt(1.0, QColor(theme.PALETTE["orange_deep"]))
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(rect, 11, 11)

        painter.setFont(icon_font(int(self.height() * 0.5)))
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(rect, Qt.AlignCenter, GLYPH_EDUCATION)
        painter.end()


class NavButton(QPushButton):
    """Sidebar row with an icon, label and optional milestone badge."""

    def __init__(
        self,
        glyph: str,
        text: str,
        badge: str | None = None,
        active: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("NavButton")
        self.setFixedHeight(46)
        self.setProperty("active", "true" if active else "false")
        self.setCursor(Qt.PointingHandCursor)

        row = QHBoxLayout(self)
        row.setContentsMargins(13, 0, 11, 0)
        row.setSpacing(11)

        icon = QLabel(glyph, self)
        icon.setFixedWidth(18)
        icon.setAlignment(Qt.AlignCenter)
        icon.setObjectName("NavIconActive" if active else "NavIcon")
        icon.setStyleSheet(
            "background: transparent;"
            "font-family: 'Segoe MDL2 Assets'; font-size: 15px;"
        )
        row.addWidget(icon)
        self._icon = icon

        label = QLabel(text, self)
        label.setObjectName("NavTextActive" if active else "NavText")
        row.addWidget(label)
        row.addStretch(1)
        self._label = label

        if badge:
            tag = QLabel(badge, self)
            tag.setObjectName("NavBadge")
            row.addWidget(tag)

    def set_active(self, active: bool) -> None:
        """Flip selection styling; the icon colour follows the object name."""
        self.setProperty("active", "true" if active else "false")
        self._icon.setObjectName("NavIconActive" if active else "NavIcon")
        self._label.setObjectName("NavTextActive" if active else "NavText")
        for widget in (self, self._icon, self._label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)


class ActionTile(QPushButton):
    """Quick-action tile. Coloured icon, title, subtitle and milestone badge."""

    def __init__(
        self,
        glyph: str,
        title: str,
        subtitle: str,
        badge: str | None,
        tint: str,
        accent: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ActionTile")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(170)
        self.setFixedHeight(64)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 9, 9, 9)
        row.setSpacing(9)

        icon = QLabel(glyph, self)
        icon.setFixedSize(32, 32)
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(
            f"background: {tint}; color: {accent}; border-radius: 9px; "
            "font-family: 'Segoe MDL2 Assets'; font-size: 14px;"
        )
        row.addWidget(icon, 0, Qt.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(2)
        name = QLabel(title, self)
        name.setObjectName("TileTitle")
        name.setWordWrap(True)
        detail = QLabel(subtitle, self)
        detail.setObjectName("TileSub")
        detail.setWordWrap(True)
        text.addWidget(name)
        text.addWidget(detail)
        text.addStretch(1)
        row.addLayout(text, 1)

        if badge:
            tag = QLabel(badge, self)
            tag.setObjectName("TileBadge")
            row.addWidget(tag, 0, Qt.AlignTop)


class ChatInput(QPlainTextEdit):
    """Enter sends, Shift+Enter adds a line."""

    submitted = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (
            event.modifiers() & Qt.ShiftModifier
        ):
            event.accept()
            self.submitted.emit()
            return
        super().keyPressEvent(event)


class TurnWidget(QWidget):
    """One conversation turn: gradient user bubble, light assistant card."""

    def __init__(self, turn: Turn, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._turn = turn
        self._copy: QToolButton | None = None
        self._bubble: QFrame | None = None
        self._metrics: QFontMetrics | None = None
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        if turn.role == "user":
            self._build_user()
        else:
            self._build_assistant()

    def _natural_width(self) -> int:
        assert self._metrics is not None
        return self._metrics.horizontalAdvance(self._turn.text) + 38

    def _apply_user_width(self) -> None:
        available = max(200, self.width() - 8)
        width = max(190, min(self._natural_width(), available))
        if self._bubble is not None:
            self._bubble.setFixedWidth(width)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._turn.role == "user":
            self._apply_user_width()
        super().resizeEvent(event)

    def _build_user(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 6, 0, 6)
        outer.addStretch(1)

        bubble = QFrame(self)
        bubble.setObjectName("UserBubble")
        inner = QVBoxLayout(bubble)
        inner.setContentsMargins(14, 9, 14, 10)
        inner.setSpacing(3)

        label = QLabel("YOU", bubble)
        label.setObjectName("UserLabel")
        inner.addWidget(label)

        body = QLabel(self._turn.text, bubble)
        body.setObjectName("UserBody")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._metrics = QFontMetrics(body.font())
        inner.addWidget(body)

        self._bubble = bubble
        outer.addWidget(bubble, 0)

    def _build_assistant(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 10, 0, 10)
        outer.setSpacing(10)

        avatar = QLabel(GLYPH_EDUCATION, self)
        avatar.setFixedSize(28, 28)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setObjectName("TurnAvatar")
        avatar.setStyleSheet(
            "background: " + theme.GRADIENT_SEND + "; color: #FFFFFF; "
            "border-radius: 14px; font-family: 'Segoe MDL2 Assets'; font-size: 12px;"
        )
        outer.addWidget(avatar, 0, Qt.AlignTop)

        column = QVBoxLayout()
        column.setSpacing(5)
        outer.addLayout(column, 1)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = "SCHOLARPATH"
        # The served model stays in the logs; students do not need provider names.
        label = QLabel(title, self)
        label.setObjectName("ErrLabel" if self._turn.error else "AsstLabel")
        header.addWidget(label)
        header.addStretch(1)

        self._copy = QToolButton(self)
        self._copy.setObjectName("Copy")
        self._copy.setText("Copy")
        self._copy.setCursor(Qt.PointingHandCursor)
        self._copy.setToolTip("Copy this reply")
        self._copy.setVisible(False)
        self._copy.clicked.connect(self._copy_text)
        header.addWidget(self._copy)
        column.addLayout(header)

        if self._turn.error:
            block = QFrame(self)
            block.setObjectName("ErrorBlock")
            inner = QVBoxLayout(block)
            inner.setContentsMargins(14, 10, 14, 10)
            body = QLabel(self._turn.text, block)
            body.setObjectName("ErrBody")
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextSelectableByMouse)
            inner.addWidget(body)
            column.addWidget(block)
        else:
            block = QFrame(self)
            block.setObjectName("AsstBubble")
            inner = QVBoxLayout(block)
            inner.setContentsMargins(14, 10, 14, 11)
            # The bubble reads like a person wrote it: markdown symbols never
            # reach the student (G131).
            body = QLabel(humanize_reply(self._turn.text), block)
            body.setObjectName("AsstBody")
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextSelectableByMouse)
            inner.addWidget(body)
            column.addWidget(block)

        column.addStretch(1)

    def _copy_text(self) -> None:
        QApplication.clipboard().setText(humanize_reply(self._turn.text))
        if self._copy is not None:
            self._copy.setText("Copied")
            self._copy.setStyleSheet(f"color: {theme.PALETTE['mint']};")

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._copy is not None:
            self._copy.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._copy is not None:
            self._copy.setVisible(False)
            self._copy.setText("Copy")
            self._copy.setStyleSheet("")
        super().leaveEvent(event)


class PrivacyGate(QWidget):
    """Wraps a control that privacy keeps off.

    The inner control is genuinely disabled (so it cannot act), but a disabled
    child does not take mouse events, so the wrapper receives the click and
    opens the place that explains the switch. While privacy is on the wrapper
    is transparent and the real control behaves normally.
    """

    clicked = Signal()

    def __init__(self, button: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._button = button
        self._button_tip = button.toolTip()
        self._gated = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        button.setParent(self)
        layout.addWidget(button)
        self.setFocusPolicy(Qt.NoFocus)
        # A transparent shield sits over the disabled control. Qt skips
        # disabled children when hit-testing; the shield makes the click
        # target explicit instead of relying on event propagation.
        self._shield = QWidget(self)
        self._shield.setAttribute(Qt.WA_NoSystemBackground, True)
        self._shield.setStyleSheet("background: transparent;")
        self._shield.installEventFilter(self)
        self._shield.hide()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._shield.setGeometry(self.rect())
        super().resizeEvent(event)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API
        if watched is self._shield and self._gated:
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    self.setFocus(Qt.MouseFocusReason)
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                if (
                    event.button() == Qt.LeftButton
                    and self._shield.rect().contains(event.position().toPoint())
                ):
                    self.clicked.emit()
                    return True
            elif event.type() == QEvent.Type.KeyPress and event.key() in (
                Qt.Key_Return,
                Qt.Key_Enter,
                Qt.Key_Space,
            ):
                self.clicked.emit()
                return True
        return super().eventFilter(watched, event)

    def set_gated(self, gated: bool, reason: str = "Off. Turn on in Settings > Privacy") -> None:
        self._gated = gated
        self._button.setEnabled(not gated)
        self._button.setToolTip(reason if gated else self._button_tip)
        self.setToolTip(reason if gated else "")
        self.setCursor(Qt.PointingHandCursor if gated else Qt.ArrowCursor)
        self.setFocusPolicy(Qt.StrongFocus if gated else Qt.NoFocus)
        self._shield.setToolTip(reason if gated else "")
        self._shield.setCursor(Qt.PointingHandCursor if gated else Qt.ArrowCursor)
        self._shield.setFocusPolicy(Qt.NoFocus)
        if gated:
            self._shield.setGeometry(self.rect())
            self._shield.show()
            self._shield.raise_()
            self.setAccessibleName(self._button.accessibleName() or "Unavailable")
            self.setAccessibleDescription(reason)
        else:
            self._shield.hide()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._gated and event.button() == Qt.LeftButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if (
            self._gated
            and event.button() == Qt.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        if self._gated and event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class ElidedStatusLabel(QLabel):
    """A one-line status that elides only between words.

    ``text()`` is what is painted (possibly with an ellipsis); ``full_text()``
    and the tooltip always keep the complete sentence.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def full_text(self) -> str:
        return self._full_text

    def set_full_text(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._apply_elision()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._apply_elision()

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API
        hint = super().minimumSizeHint()
        return QSize(0, hint.height())

    def _apply_elision(self) -> None:
        text = self._full_text
        width = self.width() - 2
        if not text or width <= 0:
            super().setText(text)
            return
        metrics = self.fontMetrics()
        if metrics.horizontalAdvance(text) <= width:
            super().setText(text)
            return
        words = text.split()
        while words:
            candidate = " ".join(words) + " \u2026"
            if metrics.horizontalAdvance(candidate) <= width:
                super().setText(candidate)
                return
            words.pop()
        # One unbroken word wider than the strip: character elision is the
        # only remaining option and still beats drawing over the next widget.
        super().setText(metrics.elidedText(text, Qt.ElideRight, width))


class MainWindow(QMainWindow):
    def __init__(
        self,
        controller: ChatController,
        config: AppConfig,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._config = config
        self._error_text: str | None = None
        self._notice: str | None = None
        self._turns = 0
        self._page_name = "chat"
        self._database = Database(database_path())
        self._scroll_timer = QTimer(self)  # deferred auto-scroll (G130)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._apply_scroll_to_bottom)
        self._voice_mode = False
        self._voice_misses = 0
        self._voice_workers: set[QThread] = set()  # held until each thread ends
        self._refresh_worker = None  # the background re-check job (G152)
        self._reminders = None  # the deadline reminder service (G156)

        self.setWindowTitle("ScholarPath AI")
        self.resize(config.ui.window_width, config.ui.window_height)
        self.setMinimumSize(1120, 720)
        self.setStyleSheet(theme.stylesheet())

        root = QWidget(self)
        root.setObjectName("Root")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())

        content = QWidget(root)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self._build_top_bar())
        content_layout.addWidget(self._build_body(), 1)
        content_layout.addWidget(self._build_status_strip())
        layout.addWidget(content, 1)

        self.setCentralWidget(root)
        self._connect()
        self._refresh_status()
        self._start_background_refresh()
        self._start_refresh_timer()
        QTimer.singleShot(2000, self._show_due_reminders)

    # -- sidebar ----------------------------------------------------------
    def _build_sidebar(self) -> QWidget:
        side = QWidget(self)
        side.setObjectName("Sidebar")
        side.setFixedWidth(240)
        column = QVBoxLayout(side)
        column.setContentsMargins(16, 22, 16, 18)
        column.setSpacing(8)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        brand.addWidget(LogoMark(38, side), 0, Qt.AlignTop)

        names = QVBoxLayout()
        names.setSpacing(1)
        name = QLabel("ScholarPath AI", side)
        name.setObjectName("BrandName")
        tagline = QLabel("Funded education, verified.", side)
        tagline.setObjectName("BrandTag")
        names.addWidget(name)
        names.addWidget(tagline)
        brand.addLayout(names, 1)
        column.addLayout(brand)
        column.addSpacing(20)

        section = QLabel("WORKSPACE", side)
        section.setObjectName("RailSection")
        column.addWidget(section)

        self._nav_buttons: dict[str, NavButton] = {}

        chat_item = NavButton(GLYPH_CHAT, "Chat Assistant", active=True, parent=side)
        chat_item.clicked.connect(lambda: self.select_page("chat"))
        column.addWidget(chat_item)
        self._nav_buttons["chat"] = chat_item

        profile_item = NavButton(GLYPH_PERSON, "My Profile", parent=side)
        profile_item.setToolTip(
            "Your academic details - local-only, filled by you or confirmed "
            "from your documents."
        )
        profile_item.clicked.connect(lambda: self.select_page("profile"))
        column.addWidget(profile_item)
        self._nav_buttons["profile"] = profile_item

        documents_item = NavButton(GLYPH_DOCUMENT, "Documents", parent=side)
        documents_item.setToolTip(
            "Upload a transcript or marksheet; extracted values are confirmed "
            "by you before they are saved."
        )
        documents_item.clicked.connect(lambda: self.select_page("documents"))
        column.addWidget(documents_item)
        self._nav_buttons["documents"] = documents_item

        research_item = NavButton(GLYPH_EDUCATION, "Scholarships", parent=side)
        research_item.setToolTip(
            "Paste an official scholarship page URL; values are verified against "
            "the page text before anything is saved. Discover searches what is "
            "already stored."
        )
        research_item.clicked.connect(lambda: self.select_page("research"))
        column.addWidget(research_item)
        self._nav_buttons["research"] = research_item

        catalog_item = NavButton(GLYPH_GLOBE, "Catalog", parent=side)
        catalog_item.setToolTip(
            "Read the official portals one by one and store what their pages "
            "state. Every value is verified word-for-word against the page."
        )
        catalog_item.clicked.connect(lambda: self.select_page("catalog"))
        column.addWidget(catalog_item)
        self._nav_buttons["catalog"] = catalog_item

        discover_item = NavButton(GLYPH_SEARCH, "Discover", parent=side)
        discover_item.setToolTip(
            "Search and filter the catalog records by what the pages state, "
            "then check one against your profile. Nothing leaves this device."
        )
        discover_item.clicked.connect(lambda: self.select_page("discover"))
        column.addWidget(discover_item)
        self._nav_buttons["discover"] = discover_item

        eligibility_item = NavButton(GLYPH_CHECK, "Eligibility", parent=side)
        eligibility_item.setToolTip(
            "Rule-based checks of your saved records against your profile - "
            "no model, no probabilities, honest unknowns."
        )
        eligibility_item.clicked.connect(lambda: self.select_page("eligibility"))
        column.addWidget(eligibility_item)
        self._nav_buttons["eligibility"] = eligibility_item

        saved_item = NavButton(GLYPH_STAR, "Saved Opportunities", parent=side)
        saved_item.setToolTip(
            "Records you explicitly saved, side-by-side comparison and "
            "application checklists. Nothing is auto-saved."
        )
        saved_item.clicked.connect(lambda: self.select_page("saved"))
        column.addWidget(saved_item)
        self._nav_buttons["saved"] = saved_item

        settings = NavButton(GLYPH_SETTING, "Settings", parent=side)
        settings.setToolTip("Config, model status, local data, and MCP tools.")
        settings.clicked.connect(lambda: self.select_page("settings"))
        column.addWidget(settings)
        self._nav_buttons["settings"] = settings

        column.addStretch(1)

        card = QFrame(side)
        card.setObjectName("SidebarCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 15, 16, 15)
        card_layout.setSpacing(4)

        mark = QLabel("S", card)
        mark.setFixedSize(34, 34)
        mark.setAlignment(Qt.AlignCenter)
        mark.setStyleSheet(
            "background: #FFE3D4; color: #E8481A; "
            "border-radius: 10px; font-size: 16px; font-weight: 700;"
        )
        card_layout.addWidget(mark)
        card_layout.addSpacing(4)

        title = QLabel("Better guidance.", card)
        title.setObjectName("SidebarCardTitle")
        card_layout.addWidget(title)

        body = QLabel(
            "Bigger opportunities.\nLocal-first and private by design.", card
        )
        body.setObjectName("SidebarCardBody")
        body.setWordWrap(True)
        card_layout.addWidget(body)
        column.addWidget(card)
        return side

    # -- top bar ----------------------------------------------------------
    def _build_top_bar(self) -> QWidget:
        bar = QWidget(self)
        bar.setObjectName("TopBar")
        bar.setFixedHeight(76)
        row = QHBoxLayout(bar)
        row.setContentsMargins(24, 0, 24, 0)
        row.setSpacing(12)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("Chat Assistant", bar)
        title.setObjectName("PageTitle")
        self._page_title = title
        self.subtitle = QLabel("Starting\u2026", bar)
        self.subtitle.setObjectName("PageSub")
        self.subtitle.setWordWrap(True)
        titles.addWidget(title)
        titles.addWidget(self.subtitle)
        row.addLayout(titles)
        row.addStretch(1)

        pill = QLabel("\u25cf  \u2026", bar)
        pill.setObjectName("StatusPill")
        self.pill = pill
        # Align instead of stretch: the chip must stay its own small height,
        # not fill the 76px top bar.
        row.addWidget(pill, 0, Qt.AlignVCenter)

        self.voice_mode_button = QToolButton(bar)
        self.voice_mode_button.setObjectName("VoiceModeButton")
        self.voice_mode_button.setText(" Live voice")
        self.voice_mode_button.setCheckable(True)
        self.voice_mode_button.setCursor(Qt.PointingHandCursor)
        self.voice_mode_button.setToolTip(
            "Live voice mode - talk hands-free: the app listens, sends your "
            "words to the model, and speaks the reply aloud. The voice is a "
            "neural one (Microsoft Edge voices, online, no key); if that is "
            "unavailable the offline Windows voice is used. Click again to end."
        )
        self.voice_mode_button.clicked.connect(self._toggle_voice_mode)
        self._voice_gate = PrivacyGate(self.voice_mode_button, bar)
        self._voice_gate.clicked.connect(self._open_privacy_settings)
        row.addWidget(self._voice_gate, 0, Qt.AlignVCenter)

        self._avatar = QLabel(GLYPH_PERSON, bar)
        self._avatar.setObjectName("Avatar")
        self._avatar.setFixedSize(34, 34)
        self._avatar.setAlignment(Qt.AlignCenter)
        self._avatar.setToolTip("No profile saved yet. Open My Profile.")
        row.addWidget(self._avatar)
        return bar

    # -- body -------------------------------------------------------------
    def _build_body(self) -> QWidget:
        holder = QWidget(self)
        row = QHBoxLayout(holder)
        row.setContentsMargins(24, 20, 24, 14)
        row.setSpacing(18)

        self._pages = QStackedWidget(holder)

        from scholarpath.ui.documents_page import DocumentsPage
        from scholarpath.ui.profile_page import ProfilePage

        chat_body = QWidget(self)
        chat_row = QHBoxLayout(chat_body)
        chat_row.setContentsMargins(0, 0, 0, 0)
        chat_row.setSpacing(18)
        chat_row.addWidget(self._build_chat_column(), 1)
        chat_row.addWidget(self._build_right_panel())
        self._pages.addWidget(chat_body)

        self._profile_page = ProfilePage(
            self._database, on_saved=self._on_profile_saved, parent=self
        )
        self._profile_scroll = QScrollArea(self)
        self._profile_scroll.setObjectName("ProfileScroll")
        self._profile_scroll.setWidgetResizable(True)
        self._profile_scroll.setFrameShape(QFrame.NoFrame)
        self._profile_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._profile_scroll.setWidget(self._profile_page)
        self._pages.addWidget(self._profile_scroll)

        self._documents_page = DocumentsPage(
            self._database,
            self._controller.gateway,
            self._config.gateway.model or None,
            on_profile_changed=self._on_profile_saved,
            parent=self,
        )
        self._pages.addWidget(self._documents_page)

        from scholarpath.ui.research_page import ResearchPage

        self._research_page = ResearchPage(
            self._database,
            self._controller.gateway,
            self._config.gateway.model or None,
            on_saved=self._on_profile_saved,
            parent=self,
        )
        self._pages.addWidget(self._research_page)

        from scholarpath.ui.eligibility_page import EligibilityPage

        self._recheck_store = RecheckStore()
        self._eligibility_page = EligibilityPage(
            self._database,
            on_open_profile=lambda: self.select_page("profile"),
            recheck_store=self._recheck_store,
            trusted_domains=self._config.search.trusted_domains,
            parent=self,
        )
        self._pages.addWidget(self._eligibility_page)

        from scholarpath.ui.catalog_page import CatalogPage

        self._catalog_page = CatalogPage(
            self._database,
            self._controller.gateway,
            self._config.gateway.model or None,
            trusted_domains=self._config.search.trusted_domains,
            parent=self,
        )
        self._pages.addWidget(self._catalog_page)

        from scholarpath.ui.discover_page import DiscoverPage

        self._discover_page = DiscoverPage(
            self._database,
            trusted_domains=self._config.search.trusted_domains,
            parent=self,
        )
        self._pages.addWidget(self._discover_page)

        from scholarpath.ui.saved_page import SavedPage

        self._saved_page = SavedPage(
            self._database,
            recheck_store=self._recheck_store,
            gateway=self._controller.gateway,
            model=self._config.gateway.model or None,
            trusted_domains=self._config.search.trusted_domains,
            parent=self,
        )
        self._pages.addWidget(self._saved_page)

        from scholarpath.ui.settings_page import SettingsPage

        self._settings_page = SettingsPage(
            self._config,
            gateway_name=lambda: self._controller.gateway_name,
            stats=self._database.counts,
            parent=self,
        )
        self._pages.addWidget(self._settings_page)

        row.addWidget(self._pages, 1)
        return holder

    def _build_chat_column(self) -> QWidget:
        column_widget = QWidget(self)
        column = QVBoxLayout(column_widget)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        self.transcript = QScrollArea(column_widget)
        self.transcript.setObjectName("Transcript")
        self.transcript.setWidgetResizable(True)
        self.transcript.setFrameShape(QFrame.NoFrame)
        self.transcript.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        body = QWidget(self.transcript)
        body.setObjectName("TranscriptBody")
        self._turns_layout = QVBoxLayout(body)
        self._turns_layout.setContentsMargins(0, 0, 6, 8)
        self._turns_layout.setSpacing(0)
        self._turns_layout.addStretch(1)

        self.empty_state = self._build_empty_state(body)
        self._turns_layout.insertWidget(0, self.empty_state)
        self.transcript.setWidget(body)
        self._stick_to_bottom = True
        scrollbar = self.transcript.verticalScrollBar()
        scrollbar.valueChanged.connect(self._on_transcript_scrolled)
        scrollbar.rangeChanged.connect(self._on_transcript_range_changed)
        column.addWidget(self.transcript, 1)
        column.addWidget(self._build_composer())
        return column_widget

    # -- transcript auto-scroll (G130) ---------------------------------------
    def _on_transcript_scrolled(self, value: int) -> None:
        """Remember whether the student is parked at the bottom of the chat."""
        scrollbar = self.transcript.verticalScrollBar()
        self._stick_to_bottom = should_stick_to_bottom(
            scrollbar.maximum(), value
        )
        if not self._stick_to_bottom:
            # The student scrolled up to read: cancel any pending re-pin, so
            # a late layout change cannot yank the view back down.
            self._scroll_timer.stop()

    def _on_transcript_range_changed(self, minimum: int, maximum: int) -> None:
        """Follow new content while the student is at the bottom (G130)."""
        if getattr(self, "_stick_to_bottom", True):
            self._scroll_transcript_to_bottom()

    def _scroll_transcript_to_bottom(self) -> None:
        """Scroll after the layout has grown, so the newest line is visible."""
        if not getattr(self, "_stick_to_bottom", True):
            return
        self._scroll_timer.start(0)  # single shot, cancelled if the user scrolls

    def _apply_scroll_to_bottom(self) -> None:
        if not getattr(self, "_stick_to_bottom", True):
            return
        scrollbar = self.transcript.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _build_empty_state(self, parent: QWidget) -> QWidget:
        holder = QWidget(parent)
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 4)
        column.setSpacing(12)

        hero = QFrame(holder)
        hero.setObjectName("HeroCard")
        row = QHBoxLayout(hero)
        row.setContentsMargins(20, 18, 20, 18)
        row.setSpacing(16)

        avatar = QLabel(GLYPH_EDUCATION, hero)
        avatar.setFixedSize(52, 52)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setObjectName("HeroAvatar")
        avatar.setStyleSheet(
            "background: " + theme.GRADIENT_SEND + "; color: #FFFFFF; "
            "border-radius: 26px; font-family: 'Segoe MDL2 Assets'; font-size: 22px;"
        )
        row.addWidget(avatar, 0, Qt.AlignTop)

        words = QVBoxLayout()
        words.setSpacing(4)
        title = QLabel("Hello.", hero)
        title.setObjectName("HeroTitle")
        sub = QLabel(
            "I can chat with you, build your academic profile from documents, "
            "search the web for current scholarships, verify the official "
            "pages, run rule-based eligibility checks, and keep your saved "
            "opportunities and checklists.",
            hero,
        )
        sub.setObjectName("HeroSub")
        sub.setWordWrap(True)
        words.addWidget(title)
        words.addWidget(sub)
        row.addLayout(words, 1)
        column.addWidget(hero)

        tiles = QWidget(holder)
        grid = QGridLayout(tiles)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        for index, (
            title_text,
            subtitle,
            _milestone,
            glyph,
            tint,
            accent,
        ) in enumerate(ACTION_TILES):
            tile = ActionTile(
                glyph,
                title_text,
                subtitle,
                None,
                tint,
                accent,
                tiles,
            )
            if title_text == "Upload Documents":
                tile.setToolTip("Open the documents page to upload and extract.")
                tile.clicked.connect(lambda _checked=False: self.select_page("documents"))
            elif title_text == "Find Scholarships":
                tile.setToolTip(
                    "Open Discover to search the verified scholarship catalog."
                )
                tile.clicked.connect(lambda _checked=False: self._find_scholarships())
            elif title_text == "Check Eligibility":
                tile.setToolTip(
                    "Deterministic checks of your saved records against your profile."
                )
                tile.clicked.connect(
                    lambda _checked=False: self.select_page("eligibility")
                )
            else:  # Explore Countries
                tile.setToolTip(
                    "Browse the stored catalog by country, level and deadline."
                )
                tile.clicked.connect(
                    lambda _checked=False: self.select_page("discover")
                )
            grid.addWidget(tile, index // 2, index % 2)
        column.addWidget(tiles)
        column.addStretch(1)
        return holder

    def _build_composer(self) -> QWidget:
        panel = QWidget(self)
        column = QVBoxLayout(panel)
        column.setContentsMargins(0, 12, 0, 0)
        column.setSpacing(6)

        self.composer = QFrame(panel)
        self.composer.setObjectName("Composer")
        self.composer.setProperty("focused", "false")
        row = QHBoxLayout(self.composer)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(4)

        self.attach = QToolButton(self.composer)
        self.attach.setObjectName("Attach")
        self.attach.setText(GLYPH_ATTACH)
        self.attach.setFixedSize(36, 36)
        self.attach.setCursor(Qt.PointingHandCursor)
        self.attach.setToolTip("Upload a document (transcript, marksheet, test report)")
        self.attach.setStyleSheet("font-family: 'Segoe MDL2 Assets'; font-size: 15px;")
        self.attach.clicked.connect(lambda: self.select_page("documents"))

        self.mic_button = MicButton(self.composer)
        self.mic_button.setObjectName("Mic")
        usable, voice_reason = availability()
        self.mic_button.setToolTip(
            "Voice input - click, then speak. Transcribed by the "
            "SpeechRecognition library (audio is sent to Google's free speech "
            "service). Your words come back here as text, and the model "
            "receives only that text. Click again to stop early."
            if usable
            else f"Voice input is unavailable: {voice_reason} Clicking shows "
            "this notice; typing still works."
        )
        self.mic_button.clicked.connect(self._toggle_voice)
        if not self._voice_stt_allowed():
            self.mic_button.setToolTip(
                "Voice input is off in this build. Turn on privacy.voice_stt in "
                "Settings to let a short microphone clip reach Google's speech "
                "service for transcription."
            )
        self._mic_gate = PrivacyGate(self.mic_button, self.composer)
        self._mic_gate.clicked.connect(self._open_privacy_settings)

        self.input = ChatInput(self.composer)
        self.input.setObjectName("Input")
        self.input.setPlaceholderText("Type your message\u2026")
        self.input.setFixedHeight(44)

        self.send_button = QPushButton(GLYPH_SEND, self.composer)
        self.send_button.setObjectName("Send")
        self.send_button.setFixedSize(40, 40)
        self.send_button.setCursor(Qt.PointingHandCursor)
        self.send_button.setToolTip("Send (Enter)")
        self.send_button.setStyleSheet(
            "font-family: 'Segoe MDL2 Assets'; font-size: 15px;"
        )

        row.addWidget(self.attach, 0, Qt.AlignVCenter)
        row.addWidget(self._mic_gate, 0, Qt.AlignVCenter)
        row.addWidget(self.input, 1)
        row.addWidget(self.send_button, 0, Qt.AlignVCenter)
        column.addWidget(self.composer)

        self.voice_bar = QFrame(panel)
        self.voice_bar.setObjectName("VoiceBar")
        bar_row = QHBoxLayout(self.voice_bar)
        bar_row.setContentsMargins(14, 10, 10, 10)
        bar_row.setSpacing(10)
        state_column = QVBoxLayout()
        state_column.setContentsMargins(0, 0, 0, 0)
        state_column.setSpacing(1)
        self.voice_state = QLabel("Listening \u2014 speak now", self.voice_bar)
        self.voice_state.setObjectName("VoiceState")
        state_column.addWidget(self.voice_state)
        self.voice_detail = QLabel("Your words become text; the reply is spoken aloud.", self.voice_bar)
        self.voice_detail.setObjectName("VoiceDetail")
        state_column.addWidget(self.voice_detail)
        bar_row.addLayout(state_column, 1)
        self.voice_end = QToolButton(self.voice_bar)
        self.voice_end.setObjectName("VoiceEnd")
        self.voice_end.setText("End")
        self.voice_end.setCursor(Qt.PointingHandCursor)
        self.voice_end.clicked.connect(lambda: self._end_voice_mode("Voice mode off."))
        bar_row.addWidget(self.voice_end, 0, Qt.AlignVCenter)
        self.voice_bar.hide()
        column.addWidget(self.voice_bar)

        self.hint = QLabel(panel)
        self.hint.setObjectName("Hint")
        self.hint.setWordWrap(True)
        column.addWidget(self.hint)
        return panel

    # -- right panel ------------------------------------------------------
    def _build_right_panel(self) -> QWidget:
        scroll = QScrollArea(self)
        scroll.setObjectName("RightScroll")
        self._right_scroll = scroll
        scroll.setFixedWidth(322)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        holder = QWidget(scroll)
        holder.setObjectName("RightBody")
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 4, 8)
        column.setSpacing(8)

        column.addWidget(self._build_profile_card(holder))
        column.addWidget(self._build_info_card(holder))
        column.addWidget(self._build_capabilities_card(holder))
        column.addStretch(1)

        scroll.setWidget(holder)
        return scroll

    def _build_profile_card(self, parent: QWidget) -> QWidget:
        card = QFrame(parent)
        card.setObjectName("PanelCard")
        column = QVBoxLayout(card)
        column.setContentsMargins(16, 12, 16, 14)
        column.setSpacing(9)

        header = QHBoxLayout()
        title = QLabel("Your Academic Profile", card)
        title.setObjectName("CardTitle")
        header.addWidget(title)
        header.addStretch(1)
        self._profile_tag = QLabel("Local", card)
        self._profile_tag.setObjectName("CapSoon")
        self._profile_tag.setToolTip("Profile data is local; it exists as soon as you save it.")
        header.addWidget(self._profile_tag)
        column.addLayout(header)

        identity = QHBoxLayout()
        identity.setSpacing(10)
        avatar = QLabel(GLYPH_PERSON, card)
        avatar.setFixedSize(46, 46)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            "background: " + theme.GRADIENT_SEND + "; color: #FFFFFF; "
            "border-radius: 23px; font-family: 'Segoe MDL2 Assets'; font-size: 18px;"
        )
        identity.addWidget(avatar)

        naming = QVBoxLayout()
        naming.setSpacing(1)
        self._profile_name = QLabel("Not set up yet", card)
        self._profile_name.setObjectName("ProfileName")
        self._profile_detail = QLabel("Local profile \u00b7 nothing saved yet", card)
        self._profile_detail.setObjectName("ProfileSub")
        naming.addWidget(self._profile_name)
        naming.addWidget(self._profile_detail)
        identity.addLayout(naming, 1)
        column.addLayout(identity)

        track = QFrame(card)
        track.setObjectName("Track")
        track.setFixedHeight(6)
        column.addWidget(track)

        self._profile_progress = QLabel("0% complete \u2014 no profile data yet", card)
        self._profile_progress.setObjectName("TrackLabel")
        column.addWidget(self._profile_progress)

        rows = (
            ("degree", "D", "Current degree", "\u2014"),
            ("gpa", "G", "GPA", "\u2014"),
            ("ielts", "I", "IELTS", "\u2014"),
            ("countries", "C", "Preferred countries", "\u2014"),
        )
        self._profile_values: dict[str, QLabel] = {}
        for key, letter, label_text, value_text in rows:
            row = QHBoxLayout()
            row.setSpacing(9)
            badge = QLabel(letter, card)
            badge.setFixedSize(26, 26)
            badge.setAlignment(Qt.AlignCenter)
            badge.setObjectName("MiniIcon")
            row.addWidget(badge)

            words = QVBoxLayout()
            words.setSpacing(0)
            label = QLabel(label_text, card)
            label.setObjectName("RowLabel")
            value = QLabel(value_text, card)
            value.setObjectName("RowValue")
            words.addWidget(label)
            words.addWidget(value)
            self._profile_values[key] = value
            row.addLayout(words, 1)
            column.addLayout(row)
        self._refresh_profile_panel()
        return card

    def _build_info_card(self, parent: QWidget) -> QWidget:
        card = QFrame(parent)
        card.setObjectName("InfoCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 9, 12, 9)
        row.setSpacing(9)

        mark = QLabel("i", card)
        mark.setFixedSize(22, 22)
        mark.setAlignment(Qt.AlignCenter)
        mark.setStyleSheet(
            "background: #FFE1D1; color: #DD4A14; border-radius: 11px; "
            "font-weight: 700; font-size: 12px;"
        )
        row.addWidget(mark, 0, Qt.AlignTop)

        text = QLabel(
            "Document text is read on this device and sent to your model service "
            "only to propose values. Every value needs your tick before it is saved.",
            card,
        )
        text.setObjectName("InfoText")
        text.setWordWrap(True)
        row.addWidget(text, 1)
        return card

    def _build_capabilities_card(self, parent: QWidget) -> QWidget:
        card = QFrame(parent)
        card.setObjectName("PanelCard")
        column = QVBoxLayout(card)
        column.setContentsMargins(16, 9, 16, 9)
        column.setSpacing(4)

        title = QLabel("What works today", card)
        title.setObjectName("CardTitle")
        column.addWidget(title)

        rows = (
            ("conversation", "Conversation"),
            ("profile", "Profile + documents"),
            ("research", "Research"),
            ("eligibility", "Eligibility"),
            ("saved", "Saved list"),
            ("web", "Web search"),
            ("voice", "Voice"),
            ("mcp", "Tools (MCP)"),
        )
        self._capability_tags: dict[str, QLabel] = {}
        for key, name in rows:
            row = QHBoxLayout()
            row.setSpacing(8)
            label = QLabel(name, card)
            label.setObjectName("CapName")
            row.addWidget(label)
            row.addStretch(1)
            tag = QLabel("", card)
            tag.setObjectName("CapSoon")
            self._capability_tags[key] = tag
            row.addWidget(tag)
            column.addLayout(row)
        self._refresh_capabilities()
        return card

    def _refresh_capabilities(self) -> None:
        """Keep the right-panel rows in step with the config."""
        tags = getattr(self, "_capability_tags", None)
        if not tags:
            return
        live = self._controller.gateway_name != "stub"
        web = self._privacy_flag("web_search")
        stt = self._privacy_flag("voice_stt")
        tts = self._privacy_flag("voice_tts")

        def set_tag(key: str, text: str, good: bool, tip: str) -> None:
            tag = tags.get(key)
            if tag is None:
                return
            if tag.text() != text:
                tag.setText(text)
            name = "CapLive" if good else "CapSoon"
            if tag.objectName() != name:
                tag.setObjectName(name)
                tag.style().unpolish(tag)
                tag.style().polish(tag)
            tag.setToolTip(tip)

        set_tag(
            "conversation",
            "LIVE" if live else "Offline",
            live,
            "Chat replies run through the local model service."
            if live
            else "Offline preview - placeholder replies with no model behind them.",
        )
        set_tag(
            "profile",
            "LIVE",
            True,
            "Local form + documents read on this device; every value is confirmed.",
        )
        set_tag(
            "research",
            "LIVE",
            True,
            "Official pages you paste; every value is verified."
            + (
                " Web search is on for current ones."
                if web
                else " Web search is off (enable in Settings > Privacy)."
            ),
        )
        set_tag(
            "eligibility",
            "LIVE",
            True,
            "Rule-based checks of records against your profile; no probabilities.",
        )
        set_tag(
            "saved",
            "LIVE",
            True,
            "You save; side-by-side comparison and checklists are included.",
        )
        set_tag(
            "web",
            "On" if web else "Off",
            web,
            "On. A search question and the pages it returns go to DuckDuckGo."
            if web
            else "Off (enable in Settings > Privacy).",
        )
        if stt and tts:
            voice_text, voice_good = "On", True
            voice_tip = (
                "On. A microphone clip goes to Google's speech service and the "
                "reply text to Microsoft's."
            )
        elif stt or tts:
            voice_text, voice_good = "Partly", False
            voice_tip = (
                f"Voice input is {'on' if stt else 'off (enable in Settings > Privacy)'}. "
                f"Spoken replies are {'on' if tts else 'off (enable in Settings > Privacy)'}."
            )
        else:
            voice_text, voice_good = "Off", False
            voice_tip = (
                "Voice input is off (enable in Settings > Privacy). Spoken "
                "replies are off (enable in Settings > Privacy)."
            )
        set_tag("voice", voice_text, voice_good, voice_tip)
        set_tag(
            "mcp",
            "Optional",
            False,
            "Off by default; configured in config.toml.",
        )

    # -- status strip -----------------------------------------------------
    def _build_status_strip(self) -> QWidget:
        strip = QWidget(self)
        strip.setObjectName("StatusStrip")
        strip.setFixedHeight(26)
        row = QHBoxLayout(strip)
        row.setContentsMargins(24, 0, 24, 0)
        row.setSpacing(8)

        self.status = ElidedStatusLabel(strip)
        self.status.setObjectName("Status")
        row.addWidget(self.status, 1)

        path = config_path()
        # The path is too long to compete with the message; the tooltip keeps
        # it available without truncating either one (G168).
        self._config_path_label = QLabel("Config", strip)
        self._config_path_label.setObjectName("StatusPath")
        self._config_path_label.setToolTip(f"Config file: {path}")
        row.addWidget(self._config_path_label, 0)
        return strip

    # -- page selection -------------------------------------------------------
    def select_page(self, name: str) -> None:
        """Switch the centre stack and keep sidebar + header copy in step."""
        index = {
            "chat": 0,
            "profile": 1,
            "documents": 2,
            "research": 3,
            "eligibility": 4,
            "catalog": 5,
            "discover": 6,
            "saved": 7,
            "settings": 8,
        }.get(name, 0)
        self._pages.setCurrentIndex(index)
        self._page_name = name
        # The side card always mirrors what is really stored locally (G137).
        try:
            self._refresh_profile_panel()
        except Exception:  # noqa: BLE001 - a stale card must not break navigation
            logger.exception("the profile panel could not be refreshed")
        titles = {
            "chat": "Chat Assistant",
            "profile": "My Profile",
            "documents": "Documents",
            "research": "Scholarship Pages",
            "eligibility": "Eligibility",
            "catalog": "Catalog",
            "discover": "Discover",
            "saved": "Saved Opportunities",
            "settings": "Settings",
        }
        if name == "saved" and self._saved_page is not None:
            self._saved_page.reload()  # data may have changed since last visit
            self._show_due_reminders()  # a deadline may have come due (G156)
        if name == "discover" and self._discover_page is not None:
            self._discover_page.reload()  # a catalog run may have added records
        self._page_title.setText(titles.get(name, titles["chat"]))
        if getattr(self, "_voice_gate", None) is not None:
            self._voice_gate.setVisible(name == "chat")
        self._notice = None  # a switch clears stale "not available" notices
        for key, button in self._nav_buttons.items():
            button.set_active(key == name)
        self._refresh_status()

    def _on_profile_saved(self) -> None:
        """Callback after the profile form or a document apply changed data.

        Each step is guarded: a failure in one view must not leave the others
        stale, and it must be visible in the log (G137).
        """
        try:
            self._profile_page.refresh()
        except Exception:  # noqa: BLE001 - one broken view must not stop the rest
            logger.exception("the profile page could not be reloaded")
        try:
            self._refresh_profile_panel()
        except Exception:  # noqa: BLE001
            logger.exception("the profile panel could not be refreshed")
        if getattr(self, "_eligibility_page", None) is not None:
            try:
                self._eligibility_page.reload()
            except Exception:  # noqa: BLE001
                logger.exception("the eligibility page could not be reloaded")
        self._refresh_status()

    def _refresh_profile_panel(self) -> None:
        """Right-panel mini card mirrors what is really stored locally."""
        record = self._database.load_profile()
        profile, _dropped = Profile.from_payload(record["data"] if record else {})

        self._profile_name.setText(profile.student_name or "Not set up yet")
        self._refresh_avatar(profile.student_name)
        self._profile_detail.setText(
            "Local profile \u00b7 stored in this app's data folder"
        )
        self._profile_tag.setText("LIVE" if record else "Local")
        self._profile_tag.setObjectName("CapLive" if record else "CapSoon")
        for widget in (self._profile_tag, self._profile_tag):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

        complete = profile.completion()
        if complete == 0:
            progress_text = "0% complete \u2014 no profile data yet"
        else:
            progress_text = f"{complete}% complete \u2014 stored locally"
        self._profile_progress.setText(progress_text)

        degree_text = "\u2014"
        if profile.degree_level:
            degree_text = DEGREE_LABELS.get(
                profile.degree_level, profile.degree_level
            )
        gpa_text = "\u2014"
        if profile.gpa:
            gpa_text = profile.gpa
            if profile.gpa_scale and profile.gpa_scale != "unknown":
                gpa_text += f" (scale {profile.gpa_scale})"
        values = {
            "degree": degree_text,
            "gpa": gpa_text,
            "ielts": profile.ielts or "\u2014",
            "countries": profile.preferred_countries or "\u2014",
        }
        for key, label in self._profile_values.items():
            label.setText(values.get(key, "\u2014"))

    def _refresh_avatar(self, name: str) -> None:
        """The top-right avatar: the profile's first letter, or a person icon."""
        avatar = getattr(self, "_avatar", None)
        if avatar is None:
            return
        stripped = (name or "").strip()
        letter = ""
        if stripped:
            first = stripped[0]
            letter = first.upper() if first.isalpha() else ""
            if not letter:
                letter = next((ch.upper() for ch in stripped if ch.isalpha()), "")
        if letter:
            avatar.setText(letter)
            avatar.setStyleSheet("")
            avatar.setToolTip(f"Your profile: {stripped}")
            avatar.setAccessibleName("Profile avatar")
        else:
            avatar.setText(GLYPH_PERSON)
            avatar.setStyleSheet(
                "font-family: 'Segoe MDL2 Assets'; font-size: 17px;"
            )
            avatar.setToolTip("No profile saved yet. Open My Profile.")
            avatar.setAccessibleName("No profile saved")

    # -- wiring -----------------------------------------------------------
    def _connect(self) -> None:
        self.send_button.clicked.connect(self._submit)
        self.input.submitted.connect(self._submit)
        self.input.installEventFilter(self)
        self._controller.turn_added.connect(self._on_turn_added)
        self._controller.busy_changed.connect(self._on_busy_changed)
        self._controller.failed.connect(self._on_failed)
        self._controller.search_started.connect(self._on_search_started)
        self._speaker = Speaker(self)
        self._speaker.finished.connect(self._on_speech_finished)
        self._speaker.failed.connect(self._on_speech_failed)
        self._speaker.engine_changed.connect(self._on_voice_engine)

    # -- freshness and reminders (Phase 3) ----------------------------------
    def _records_due(self, records: list[dict]) -> bool:
        """True when a record's last check is older than the configured age."""
        limit = datetime.now(timezone.utc) - timedelta(
            hours=self._config.freshness.interval_hours
        )
        for record in records:
            checked = str((record.get("data") or {}).get("last_checked_at") or "")
            if not checked:
                return True
            try:
                moment = datetime.fromisoformat(checked)
            except ValueError:
                return True
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            if moment < limit:
                return True
        return False

    def _start_background_refresh(self) -> None:
        """Check the stored records in the background when one is due."""
        if not self._config.freshness.auto:
            return
        worker = getattr(self, "_refresh_worker", None)
        if worker is not None and worker.isRunning():
            return
        try:
            records = list(self._database.catalog_records())
        except Exception:  # noqa: BLE001 - a background job must never break the app
            return
        if not records or not self._records_due(records):
            return
        from scholarpath.ui.freshness import RefreshWorker

        self._refresh_worker = RefreshWorker(
            self._database,
            gateway=self._controller.gateway,
            model=self._config.gateway.model or None,
            max_records=self._config.freshness.max_per_run,
            parent=self,
        )
        self._refresh_worker.finished_run.connect(self._on_background_refresh)
        self._refresh_worker.start()

    def _start_refresh_timer(self) -> None:
        """Look again while the app stays open (a record becomes due over time)."""
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(30 * 60 * 1000)  # every half hour
        self._refresh_timer.timeout.connect(self._start_background_refresh)
        self._refresh_timer.start()

    def _on_background_refresh(self, stats) -> None:
        self._refresh_worker = None
        logger.info("background refresh: %s", stats.summary() if stats else "")

    def _show_due_reminders(self) -> None:
        """Show the deadline reminders that are due (opt-in, local)."""
        if not self._config.reminders.enabled:
            return
        from scholarpath.ui.reminders import ReminderService

        service = ReminderService(self._database, enabled=True)
        shown = service.show_due()
        if shown:
            logger.info("shown %d deadline reminder(s)", len(shown))

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        """Flush and release the local database; stop ingest threads."""
        if self._documents_page is not None:
            self._documents_page.cancel_worker()
        if self._research_page is not None:
            self._research_page.cancel_worker()
        if getattr(self, "_catalog_page", None) is not None:
            self._catalog_page.shutdown()
        if getattr(self, "_settings_page", None) is not None:
            self._settings_page.shutdown()
        if getattr(self, "_refresh_worker", None) is not None:
            self._refresh_worker.wait(5000)
        if getattr(self, "_profile_scan_worker", None) is not None:
            self._profile_scan_worker.wait(5000)
        if getattr(self, "_voice_worker", None) is not None:
            if self._voice_worker.isRunning():  # a mic capture cannot outlive the window
                cancel_active()
                self._voice_worker.wait(5000)
        if getattr(self, "_speaker", None) is not None:
            self._speaker.stop()
            self._speaker.wait(5)
        self._database.close()
        super().closeEvent(event)
    def _submit(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            return
        if self._controller.send(text):
            self.input.clear()

    def _find_scholarships(self) -> None:
        """The quick action opens Discover and puts the cursor in its search."""
        self.select_page("discover")
        try:
            self._discover_page.focus_search()
        except Exception:  # noqa: BLE001 - focus is a nicety, not navigation
            logger.exception("the Discover search box could not be focused")

    def _open_privacy_settings(self) -> None:
        """A gated voice control sends the student to the privacy explanation."""
        self.select_page("settings")
        page = getattr(self, "_settings_page", None)
        if page is None:
            return
        try:
            page.focus_privacy()
        except Exception:  # noqa: BLE001 - the page still opened
            logger.exception("the privacy section could not be focused")

    def _on_search_started(self, query: str) -> None:
        """Tell the student the app is searching the web right now (G136)."""
        logger.info("web search started for a %d-character query", len(query))
        self.subtitle.setText(f"Searching the web for \u201c{query}\u201d\u2026")

    def _on_turn_added(self, turn: Turn) -> None:
        if self._turns == 0:
            self.empty_state.setVisible(False)
        self._turns += 1
        self._notice = None
        if turn.role == "user":
            self._last_user_text = turn.text
        widget = TurnWidget(turn, self.transcript.widget())
        self._turns_layout.insertWidget(self._turns_layout.count() - 1, widget)
        if getattr(self, "_stick_to_bottom", True):
            self._scroll_transcript_to_bottom()  # follow the conversation (G130)
        if turn.role == "assistant" and not turn.error:
            self._maybe_scan_profile()
            if self._voice_mode_active():
                self._speak_reply(turn)
        elif turn.role == "assistant" and turn.error and self._voice_mode_active():
            # A failed reply must not end the conversation. Say what happened
            # and keep listening; the student can simply ask again (G132).
            logger.info("voice mode: reply failed; speaking a notice and listening again")
            self._speak_notice(
                "Sorry, I couldn't get an answer just then. Please ask me again."
            )
        self._refresh_status()

    # -- chat â†’ profile capture (G117) ---------------------------------------
    def _maybe_scan_profile(self) -> None:
        """Offer to save profile facts the student just stated in chat."""
        message = getattr(self, "_last_user_text", "").strip()
        if not message:
            return
        if getattr(self, "_profile_scan_worker", None) is not None:
            if self._profile_scan_worker.isRunning():
                return  # one scan at a time; the reply already landed
        self._profile_scan_worker = _ProfileScanWorker(
            message, self._controller.gateway, self._config.gateway.model or None
        )
        self._profile_scan_worker.scanned.connect(self._on_profile_scan)
        self._profile_scan_worker.start()

    def _on_profile_scan(self, updates: dict | None, _error: str) -> None:
        if not updates:
            return
        card = ProfileSuggestionCard(
            updates, self._apply_profile_suggestion, self.transcript.widget()
        )
        self._turns_layout.insertWidget(self._turns_layout.count() - 1, card)
        if getattr(self, "_stick_to_bottom", True):
            self._scroll_transcript_to_bottom()

    def _apply_profile_suggestion(self, selected: dict[str, str]) -> None:
        payload = merge_selected(
            self._database.load_profile(), selected, selected
        )
        self._database.save_profile(payload)
        self._on_profile_saved()
        self._notice = (
            "Saved to your profile \u2014 "
            + ", ".join(sorted(selected))
            + ". No need to enter these again."
        )
        self._refresh_status()

    # -- voice input (G123, G124, G125) ---------------------------------------
    def _privacy(self) -> object:
        """The privacy switches (voice_stt, voice_tts, web_search)."""
        return getattr(getattr(self, "_config", None), "privacy", None)

    def _voice_stt_allowed(self) -> bool:
        privacy = self._privacy()
        return bool(getattr(privacy, "voice_stt", False))

    def _voice_tts_allowed(self) -> bool:
        privacy = self._privacy()
        return bool(getattr(privacy, "voice_tts", False))

    def _privacy_flag(self, name: str) -> bool:
        return bool(getattr(self._privacy(), name, False))

    def _apply_privacy_gates(self) -> None:
        """Grey out what privacy keeps off, and keep it clickable to Settings."""
        stt = self._voice_stt_allowed()
        tts = self._voice_tts_allowed()
        mic_gate = getattr(self, "_mic_gate", None)
        if mic_gate is not None:
            mic_gate.set_gated(not stt)
        voice_gate = getattr(self, "_voice_gate", None)
        if voice_gate is not None:
            voice_gate.set_gated(not (stt and tts))
            if not (stt and tts):
                self.voice_mode_button.setChecked(False)
        if self._voice_mode_active() and not (stt and tts):
            self._end_voice_mode(
                "Live voice is off. Turn it on in Settings > Privacy."
            )

    def _toggle_voice(self) -> None:
        worker = getattr(self, "_voice_worker", None)
        if worker is not None and worker.isRunning():
            self.mic_button.set_listening(False)  # ripple stops immediately
            self._notice = "Stopping the microphone\u2026"
            self._refresh_status()
            cancel_active()  # second click stops the running capture
            return
        if not self._voice_stt_allowed():
            self.mic_button.set_listening(False)
            self._notice = (
                "Voice input is off. Turning it on (privacy.voice_stt in "
                "Settings) sends a short microphone clip to Google's speech "
                "service to turn it into text."
            )
            self._refresh_status()
            return
        usable, reason = availability()
        if not usable:
            self.mic_button.set_listening(False)
            self._notice = reason
            self._refresh_status()
            return
        self._error_text = None
        self._notice = "Listening \u2014 speak now, then pause. Click again to stop."
        self._voice_notice = True
        self.mic_button.set_listening(True)  # ripple starts with the capture
        self._refresh_status()
        self._voice_worker = _VoiceWorker()
        self._voice_worker.heard.connect(self._on_voice_heard)
        self._voice_worker.failed.connect(self._on_voice_failed)
        self._voice_worker.start()

    def _set_voice_not_ok(self) -> None:
        self.mic_button.set_listening(False)
        if getattr(self, "_voice_notice", False):
            self._voice_notice = False
            self._notice = None
            self._refresh_status()

    def _on_voice_heard(self, text: str) -> None:
        self._set_voice_not_ok()
        self._error_text = None
        if not text.strip():
            self._notice = "Nothing was heard. Click the mic and try again."
            self._refresh_status()
            return
        self.input.insertPlainText(text.strip() + " ")
        self.input.setFocus()
        self._notice = (
            "Voice converted to text \u2014 review it and press Enter to send."
        )
        self._refresh_status()

    def _on_voice_failed(self, message: str) -> None:
        self._set_voice_not_ok()
        # Informational, not an app error: the message says what to do next.
        self._notice = message
        self._refresh_status()

    # -- live voice mode (G126) ------------------------------------------------
    def _voice_mode_active(self) -> bool:
        return bool(getattr(self, "_voice_mode", False))

    def _toggle_voice_mode(self) -> None:
        if self._voice_mode_active():
            self._end_voice_mode("Voice mode off.")
            return
        if self._controller.chat_mode != "live":
            self.voice_mode_button.setChecked(False)
            self._notice = (
                "Voice mode needs the live model connection. Open Settings "
                "to connect, then try again."
            )
            self._refresh_status()
            return
        usable, reason = availability()
        if not usable:
            self.voice_mode_button.setChecked(False)
            self._notice = reason
            self._refresh_status()
            return
        missing = []
        if not self._voice_stt_allowed():
            missing.append("voice_stt")
        if not self._voice_tts_allowed():
            missing.append("voice_tts")
        if missing:
            self.voice_mode_button.setChecked(False)
            self._notice = (
                "Live voice is off. It needs "
                + " and ".join(f"privacy.{name}" for name in missing)
                + " turned on in Settings: the microphone clip goes to Google's "
                "speech service and the reply text to Microsoft's."
            )
            self._refresh_status()
            return
        speakable, speak_reason = Speaker.available()
        if not speakable:
            self.voice_mode_button.setChecked(False)
            self._notice = speak_reason
            self._refresh_status()
            return
        self._voice_mode = True
        self._voice_misses = 0
        self.mic_button.setEnabled(False)  # the voice bar owns the mic now
        self.voice_bar.show()
        self._scroll_transcript_to_bottom()  # the bar changed the viewport
        self._set_voice_state("Listening \u2014 speak now", "Click End to stop.")
        self._voice_mode_listen()

    def _set_voice_state(self, state: str, detail: str) -> None:
        self.voice_state.setText(state)
        self.voice_detail.setText(detail)

    def _voice_mode_listen(self) -> None:
        if not self._voice_mode_active():
            return
        logger.info("voice mode: listening")
        worker = _VoiceWorker()
        self._voice_worker = worker
        # Hold a reference until the thread really ends, so Qt never destroys
        # a QThread that is still running.
        self._voice_workers.add(worker)
        worker.finished.connect(lambda w=worker: self._voice_workers.discard(w))
        worker.heard.connect(self._on_voice_mode_heard)
        worker.failed.connect(self._on_voice_mode_failed)
        worker.start()

    def _on_voice_mode_heard(self, text: str) -> None:
        if not self._voice_mode_active():
            return
        logger.info("voice mode: heard %d characters", len(text.strip()))
        if not text.strip():
            self._on_voice_mode_miss()
            return
        self._voice_misses = 0
        sent = self._controller.send(text)
        if sent:
            self._set_voice_state("Thinking\u2026", "The model is replying; it will be spoken.")
        else:
            # The model was still replying - drop this utterance and keep the loop.
            self._set_voice_state("One moment\u2026", "Waiting for the current reply; message skipped.")
            self._retry_listen_when_free()

    def _retry_listen_when_free(self) -> None:
        def retry() -> None:
            if not self._voice_mode_active():
                return
            if self._controller.busy:
                QTimer.singleShot(500, retry)
            else:
                self._voice_mode_listen()

        QTimer.singleShot(500, retry)

    def _on_voice_mode_failed(self, message: str) -> None:
        if not self._voice_mode_active():
            return
        logger.info("voice mode: capture failed: %s", message)
        if "Nothing was heard" in message:
            self._on_voice_mode_miss()
        else:
            self._end_voice_mode(message)

    def _on_voice_mode_miss(self) -> None:
        self._voice_misses += 1
        if self._voice_misses >= 3:
            self._end_voice_mode(
                "Nothing was heard several times \u2014 voice mode stopped."
            )
        else:
            self._set_voice_state(
                "Nothing heard yet", "Speak a little louder. Click End to stop."
            )
            self._voice_mode_listen()

    def _on_speech_finished(self) -> None:
        if self._voice_mode_active():
            logger.info("voice mode: speech finished; listening again")
            self._set_voice_state("Listening \u2014 speak now", "Click End to stop.")
            self._voice_mode_listen()

    def _on_speech_failed(self, message: str) -> None:
        logger.info("voice mode: speech failed: %s", message)
        self._end_voice_mode(message)

    def _speak_reply(self, turn: Turn) -> None:
        if not self._voice_tts_allowed():
            return  # speaking is switched off: the reply stays in the chat
        speech, truncated = to_speech(turn.text)
        logger.info(
            "voice mode: speaking reply (%d characters, truncated=%s)",
            len(speech),
            truncated,
        )
        detail = "Click End to stop."
        if truncated:
            detail = "Full reply is in the chat. Click End to stop."
        self._set_voice_state("Speaking\u2026", detail)
        self._speaker.say(speech)

    def _speak_notice(self, text: str) -> None:
        """Say something short (a failure note) and keep the loop alive."""
        if not self._voice_tts_allowed():
            return
        logger.info("voice mode: speaking a notice (%d characters)", len(text))
        self._set_voice_state("Speaking\u2026", "Click End to stop.")
        self._speaker.say(text)

    def _on_voice_engine(self, engine: str) -> None:
        """Name the voice that is really speaking (G130)."""
        logger.info("voice mode: speaking with the %s engine", engine)
        if not self._voice_mode_active():
            return
        self.voice_detail.setText(
            f"Speaking with the {engine_label(engine)}. Click End to stop."
        )

    def _end_voice_mode(self, notice: str) -> None:
        if not self._voice_mode_active():
            return
        self._voice_mode = False
        cancel_active()  # stop any listening capture
        self._speaker.stop()  # silence the current utterance
        self.voice_bar.hide()
        self._scroll_transcript_to_bottom()  # the bar changed the viewport
        self.voice_mode_button.setChecked(False)
        self._apply_privacy_gates()
        if notice:
            self._notice = notice
            self._refresh_status()

    def _on_busy_changed(self, busy: bool) -> None:
        self.input.setEnabled(not busy)
        self.send_button.setEnabled(not busy)
        self.attach.setEnabled(not busy)
        if busy:
            self._error_text = None
            self._notice = None
        self._refresh_status()

    def _on_failed(self, message: str) -> None:
        self._error_text = message
        self._refresh_status()

    def _open_config_folder(self) -> None:
        folder = config_path().parent
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            self._notice = f"Could not open the config folder: {folder}"
            self._refresh_status()
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API
        if watched is self.input and event.type() in (
            QEvent.Type.FocusIn,
            QEvent.Type.FocusOut,
        ):
            focused = event.type() == QEvent.Type.FocusIn
            self.composer.setProperty("focused", "true" if focused else "false")
            style = self.composer.style()
            style.unpolish(self.composer)
            style.polish(self.composer)
        return super().eventFilter(watched, event)

    # -- status -----------------------------------------------------------
    def _refresh_status(self) -> None:
        busy = self._controller.busy

        if self._error_text is not None and not busy:
            name = "StatusErr"
            text = f"Error \u2014 {self._error_text}"
        elif self._notice is not None:
            name = "StatusWarn"
            text = self._notice
        else:
            name = "Status"
            state = "Working\u2026" if busy else "Ready"
            count = self._turns
            noun = "message" if count == 1 else "messages"
            if self._page_name == "profile":
                text = f"{state}  \u00b7  profile  \u00b7  stored locally, nothing leaves this device"
            elif self._page_name == "documents":
                text = f"{state}  \u00b7  documents  \u00b7  parsed locally, confirmed by you"
            elif self._page_name == "research":
                text = f"{state}  \u00b7  research  \u00b7  official pages only  \u00b7  verified values"
            elif self._page_name == "eligibility":
                text = (
                    f"{state}  \u00b7  eligibility  \u00b7  rule-based  \u00b7  no probabilities"
                )
            elif self._page_name == "saved":
                text = f"{state}  \u00b7  saved  \u00b7  nothing is auto-saved"
            elif self._page_name == "settings":
                text = f"{state}  \u00b7  settings  \u00b7  status only  \u00b7  config stays in config.toml"
            else:
                if not self._privacy_flag("web_search"):
                    search_state = "web search off (enable in Settings)"
                elif self._controller.last_search:
                    search_state = "web search used"
                else:
                    search_state = "no web search yet"
                text = (
                    f"{state}  \u00b7  chat: {self._controller.chat_mode}  \u00b7  "
                    f"{count} {noun}  \u00b7  {search_state}"
                )

        if self.status.objectName() != name:
            self.status.setObjectName(name)
        self.status.set_full_text(text)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

        self._apply_privacy_gates()
        self._refresh_capabilities()

        live = self._controller.gateway_name != "stub"
        # Provider names stay in the logs - students only see "live" or "offline".
        if live:
            pill_name = "StatusLive"
            pill_text = "\u25cf  Live"
        else:
            pill_name = "StatusPill"
            pill_text = "\u25cf  Offline"
        if busy:
            pill_text += " \u00b7 working"
        if self.pill.objectName() != pill_name:
            self.pill.setObjectName(pill_name)
        self.pill.setText(pill_text)
        self.pill.style().unpolish(self.pill)
        self.pill.style().polish(self.pill)

        if busy:
            self.subtitle.setText("Working on your message\u2026")
        elif self._page_name == "profile":
            self.subtitle.setText(
                "Academic profile \u2014 local-only, private by design."
            )
        elif self._page_name == "documents":
            self.subtitle.setText(
                "Documents \u2014 parsed locally, every value confirmed by you."
            )
        elif self._page_name == "research":
            self.subtitle.setText(
                "Scholarship pages \u2014 you paste the official URL; every value is verified."
            )
        elif self._page_name == "eligibility":
            self.subtitle.setText(
                "Eligibility \u2014 deterministic checks with honest unknowns."
            )
        elif self._page_name == "saved":
            self.subtitle.setText(
                "Saved Opportunities \u2014 side-by-side reading and checklists; "
                "nothing is auto-saved."
            )
        elif self._page_name == "settings":
            self.subtitle.setText(
                "Settings \u2014 an honest description of what runs and what "
                "stays local."
            )
        elif live:
            web = "on" if self._privacy_flag("web_search") else "off (enable in Settings)"
            self.subtitle.setText(f"Model replies are live \u00b7 web search {web}.")
        else:
            self.subtitle.setText(
                "Offline preview \u2014 replies are placeholder text, no model behind them."
            )

        if live:
            self.hint.setText(self._chat_hint())
        else:
            self.hint.setText(
                "Offline preview \u2014 replies are placeholder text with no model behind them."
            )

    def _chat_hint(self) -> str:
        """One honest line about the optional features, from the config."""
        web = "on" if self._privacy_flag("web_search") else "off (enable in Settings)"
        stt = "on" if self._privacy_flag("voice_stt") else "off (enable in Settings)"
        tts = "on" if self._privacy_flag("voice_tts") else "off (enable in Settings)"
        return (
            f"Web search {web}  \u00b7  voice input {stt}  \u00b7  spoken replies {tts}  "
            "\u00b7  page verification, eligibility checks and saved lists are live."
        )


class _VoiceWorker(QThread):
    """Microphone capture + transcription, off the UI thread."""

    heard = Signal(str)
    failed = Signal(str)

    def run(self) -> None:
        listen_once(self.heard.emit, self.failed.emit)


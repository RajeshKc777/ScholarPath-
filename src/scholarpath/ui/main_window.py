"""Main window: light dashboard shell for the Milestone 1 chat loop.

Layout follows the user-supplied dashboard reference: navy sidebar, top bar,
gradient welcome card, quick-action tiles, conversation column, academic
profile panel. Every value shown is real application state - the profile and
feature tiles are explicitly marked as not built yet.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QThread, QUrl, Signal
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
from scholarpath.storage import Database, database_path
from scholarpath.ui import theme
from scholarpath.ui.chat_controller import ChatController, Turn
from scholarpath.ui.profile_page import DEGREE_LABELS
from scholarpath.ui.profile_suggestion import ProfileSuggestionCard, _ProfileScanWorker
from scholarpath.voice import availability, cancel_active, listen_once

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
GLYPH_CHECK = "\uE73E"

ACTION_TILES = (
    ("Find Scholarships", "Official pages you paste", "M4", GLYPH_STAR, "#FFF1E8", "#FF4500"),
    ("Check Eligibility", "Rule-based, no gaps", "M5", GLYPH_CHECK, "#EAF9F0", "#10B981"),
    ("Explore Countries", "Where to study?", "M6", GLYPH_GLOBE, "#EAF2FF", "#3B82F6"),
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
        self.setFixedSize(170, 88)

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
            body = QLabel(self._turn.text, block)
            body.setObjectName("AsstBody")
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextSelectableByMouse)
            inner.addWidget(body)
            column.addWidget(block)

        column.addStretch(1)

    def _copy_text(self) -> None:
        QApplication.clipboard().setText(self._turn.text)
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
            "the page text before anything is saved. Search comes later."
        )
        research_item.clicked.connect(lambda: self.select_page("research"))
        column.addWidget(research_item)
        self._nav_buttons["research"] = research_item

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

        avatar = QLabel("S", bar)
        avatar.setObjectName("Avatar")
        avatar.setFixedSize(34, 34)
        avatar.setAlignment(Qt.AlignCenter)
        row.addWidget(avatar)
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
        self._pages.addWidget(self._profile_page)

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

        self._eligibility_page = EligibilityPage(
            self._database, on_open_profile=lambda: self.select_page("profile"), parent=self
        )
        self._pages.addWidget(self._eligibility_page)

        from scholarpath.ui.saved_page import SavedPage

        self._saved_page = SavedPage(self._database, parent=self)
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
        column.addWidget(self.transcript, 1)
        column.addWidget(self._build_composer())
        return column_widget

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
            "verify scholarship pages you paste here, run rule-based "
            "eligibility checks, and keep your saved opportunities and "
            "checklists. Automatic search arrives later.",
            hero,
        )
        sub.setObjectName("HeroSub")
        sub.setWordWrap(True)
        words.addWidget(title)
        words.addWidget(sub)
        row.addLayout(words, 1)
        column.addWidget(hero)

        tiles = QWidget(holder)
        flow = FlowLayout(tiles, spacing=10)
        for title_text, subtitle, milestone, glyph, tint, accent in ACTION_TILES:
            working = title_text in (
                "Upload Documents", "Find Scholarships", "Check Eligibility",
            )
            tile = ActionTile(
                glyph,
                title_text,
                subtitle,
                None if working else "Soon",
                tint,
                accent,
                tiles,
            )
            if title_text == "Upload Documents":
                tile.setToolTip("Open the documents page to upload and extract.")
                tile.clicked.connect(lambda _checked=False: self.select_page("documents"))
            elif title_text == "Find Scholarships":
                tile.setToolTip(
                    "Paste an official scholarship page URL. No automatic search yet."
                )
                tile.clicked.connect(lambda _checked=False: self.select_page("research"))
            elif title_text == "Check Eligibility":
                tile.setToolTip(
                    "Deterministic checks of your saved records against your profile."
                )
                tile.clicked.connect(
                    lambda _checked=False: self.select_page("eligibility")
                )
            else:
                tile.setToolTip(
                    f"{title_text} arrives in Milestone {milestone[1:]}. "
                    "Not available in this build."
                )
                tile.clicked.connect(
                    lambda _checked=False, name=title_text, m=milestone: self._not_available(
                        name, m
                    )
                )
            flow.addWidget(tile)
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

        self.mic_button = QToolButton(self.composer)
        self.mic_button.setObjectName("Attach")
        self.mic_button.setText(GLYPH_MIC)
        self.mic_button.setFixedSize(36, 36)
        self.mic_button.setCursor(Qt.PointingHandCursor)
        self.mic_button.setStyleSheet("font-family: 'Segoe MDL2 Assets'; font-size: 15px;")
        usable, voice_reason = availability()
        self.mic_button.setToolTip(
            "Voice input - click, then speak. Uses Windows speech recognition "
            "(online): your words come back as text here, and the model "
            "receives only that text. Click again to stop early."
            if usable
            else f"Voice input is unavailable: {voice_reason} Clicking shows "
            "this notice; typing still works."
        )
        self.mic_button.clicked.connect(self._toggle_voice)

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
        row.addWidget(self.mic_button, 0, Qt.AlignVCenter)
        row.addWidget(self.input, 1)
        row.addWidget(self.send_button, 0, Qt.AlignVCenter)
        column.addWidget(self.composer)

        self.hint = QLabel(panel)
        self.hint.setObjectName("Hint")
        column.addWidget(self.hint)
        return panel

    # -- right panel ------------------------------------------------------
    def _build_right_panel(self) -> QWidget:
        scroll = QScrollArea(self)
        scroll.setObjectName("RightScroll")
        scroll.setFixedWidth(322)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        holder = QWidget(scroll)
        holder.setObjectName("RightBody")
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 4, 8)
        column.setSpacing(12)

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
        column.setContentsMargins(16, 14, 16, 16)
        column.setSpacing(10)

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
        row.setContentsMargins(12, 10, 12, 10)
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
        column.setContentsMargins(16, 14, 16, 14)
        column.setSpacing(8)

        title = QLabel("What works today", card)
        title.setObjectName("CardTitle")
        column.addWidget(title)

        rows = (
            ("Conversation", "LIVE", True, "Chat replies run through the model gateway."),
            ("Profile", "LIVE", True, "Local form + confirmed document values."),
            ("Documents", "LIVE", True, "Upload, read locally, confirm every value."),
            ("Research", "LIVE", True, "Official pages you paste; search is not built yet."),
            ("Eligibility", "LIVE", True, "Rule-based checks of records vs your profile."),
            ("Saved list", "LIVE", True, "You save; comparison and checklists included."),
            ("Tools (MCP)", "Optional", False, "Off by default; configured in config.toml."),
        )
        for name, tag_text, live, tip in rows:
            row = QHBoxLayout()
            row.setSpacing(8)
            label = QLabel(name, card)
            label.setObjectName("CapName")
            row.addWidget(label)
            row.addStretch(1)
            tag = QLabel(tag_text, card)
            tag.setObjectName("CapLive" if live else "CapSoon")
            tag.setToolTip(tip)
            row.addWidget(tag)
            column.addLayout(row)
        return card

    # -- status strip -----------------------------------------------------
    def _build_status_strip(self) -> QWidget:
        strip = QWidget(self)
        strip.setObjectName("StatusStrip")
        strip.setFixedHeight(26)
        row = QHBoxLayout(strip)
        row.setContentsMargins(24, 0, 24, 0)
        row.setSpacing(8)

        self.status = QLabel(strip)
        self.status.setObjectName("Status")
        row.addWidget(self.status)
        row.addStretch(1)

        path = config_path()
        path_label = QLabel(self._elided_path(str(path)), strip)
        path_label.setObjectName("StatusPath")
        path_label.setToolTip(str(path))
        row.addWidget(path_label)
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
            "saved": 5,
            "settings": 6,
        }.get(name, 0)
        self._pages.setCurrentIndex(index)
        self._page_name = name
        titles = {
            "chat": "Chat Assistant",
            "profile": "My Profile",
            "documents": "Documents",
            "research": "Scholarship Pages",
            "eligibility": "Eligibility",
            "saved": "Saved Opportunities",
            "settings": "Settings",
        }
        if name == "saved" and self._saved_page is not None:
            self._saved_page.reload()  # data may have changed since last visit
        self._page_title.setText(titles.get(name, titles["chat"]))
        self._notice = None  # a switch clears stale "not available" notices
        for key, button in self._nav_buttons.items():
            button.set_active(key == name)
        self._refresh_status()

    def _on_profile_saved(self) -> None:
        """Callback after the profile form or a document apply changed data."""
        self._profile_page.refresh()
        self._refresh_profile_panel()
        if getattr(self, "_eligibility_page", None) is not None:
            self._eligibility_page.reload()
        self._refresh_status()

    def _refresh_profile_panel(self) -> None:
        """Right-panel mini card mirrors what is really stored locally."""
        record = self._database.load_profile()
        profile, _dropped = Profile.from_payload(record["data"] if record else {})

        self._profile_name.setText(profile.student_name or "Not set up yet")
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

    # -- wiring -----------------------------------------------------------
    def _connect(self) -> None:
        self.send_button.clicked.connect(self._submit)
        self.input.submitted.connect(self._submit)
        self.input.installEventFilter(self)
        self._controller.turn_added.connect(self._on_turn_added)
        self._controller.busy_changed.connect(self._on_busy_changed)
        self._controller.failed.connect(self._on_failed)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        """Flush and release the local database; stop ingest threads."""
        if self._documents_page is not None:
            self._documents_page.cancel_worker()
        if self._research_page is not None:
            self._research_page.cancel_worker()
        if getattr(self, "_settings_page", None) is not None:
            self._settings_page.shutdown()
        if getattr(self, "_profile_scan_worker", None) is not None:
            self._profile_scan_worker.wait(5000)
        if getattr(self, "_voice_worker", None) is not None:
            if self._voice_worker.isRunning():  # a mic capture cannot outlive the window
                cancel_active()
                self._voice_worker.wait(5000)
        self._database.close()
        super().closeEvent(event)
    def _submit(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            return
        if self._controller.send(text):
            self.input.clear()

    def _not_available(self, feature: str, milestone: str) -> None:
        number = milestone.lstrip("M")
        self._notice = (
            f"Not available in this build \u2014 {feature} arrives in "
            f"Milestone {number}."
        )
        self._refresh_status()

    def _on_turn_added(self, turn: Turn) -> None:
        if self._turns == 0:
            self.empty_state.setVisible(False)
        self._turns += 1
        self._notice = None
        if turn.role == "user":
            self._last_user_text = turn.text
        widget = TurnWidget(turn, self.transcript.widget())
        self._turns_layout.insertWidget(self._turns_layout.count() - 1, widget)
        self.transcript.verticalScrollBar().setValue(
            self.transcript.verticalScrollBar().maximum()
        )
        if turn.role == "assistant" and not turn.error:
            self._maybe_scan_profile()
        self._refresh_status()

    # -- chat → profile capture (G117) ---------------------------------------
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
        self.transcript.verticalScrollBar().setValue(
            self.transcript.verticalScrollBar().maximum()
        )

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

    # -- voice input (G123) ---------------------------------------------------
    def _toggle_voice(self) -> None:
        worker = getattr(self, "_voice_worker", None)
        if worker is not None and worker.isRunning():
            cancel_active()  # second click stops the running capture
            return
        usable, reason = availability()
        if not usable:
            self._notice = reason
            self._refresh_status()
            return
        self.mic_button.setEnabled(False)
        self._notice = "Listening \u2014 speak now, then pause. Click again to stop."
        self._voice_notice = True
        self._refresh_status()
        self._voice_worker = _VoiceWorker()
        self._voice_worker.heard.connect(self._on_voice_heard)
        self._voice_worker.failed.connect(self._on_voice_failed)
        self._voice_worker.start()

    def _set_voice_not_ok(self) -> None:
        self.mic_button.setEnabled(True)
        if getattr(self, "_voice_notice", False):
            self._voice_notice = False
            self._notice = None
            self._refresh_status()

    def _on_voice_heard(self, text: str) -> None:
        self._set_voice_not_ok()
        if not text.strip():
            self._notice = "Nothing was heard. Click the mic and try again."
            self._refresh_status()
            return
        self.input.insertPlainText(text.strip() + " ")
        self.input.setFocus()
        self._notice = (
            "Voice converted to text by Windows speech \u2014 review it and "
            "press Enter to send."
        )
        self._refresh_status()

    def _on_voice_failed(self, message: str) -> None:
        self._set_voice_not_ok()
        self._error_text = message
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
                text = f"{state}  \u00b7  research  \u00b7  official pages only  \u00b7  no automatic search"
            elif self._page_name == "eligibility":
                text = (
                    f"{state}  \u00b7  eligibility  \u00b7  rule-based  \u00b7  no probabilities"
                )
            elif self._page_name == "saved":
                text = f"{state}  \u00b7  saved  \u00b7  nothing is auto-saved"
            elif self._page_name == "settings":
                text = f"{state}  \u00b7  settings  \u00b7  status only  \u00b7  config stays in config.toml"
            else:
                text = (
                    f"{state}  \u00b7  chat: {self._controller.chat_mode}  \u00b7  "
                    f"{count} {noun}  \u00b7  no research performed"
                )

        if self.status.objectName() != name:
            self.status.setObjectName(name)
        self.status.setText(text)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

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
            self.subtitle.setText(
                "Model replies are live. Scholarship pages can be verified; "
                "automatic search is still to come."
            )
        else:
            self.subtitle.setText(
                "Offline preview \u2014 replies are placeholder text, no model behind them."
            )

        if live:
            self.hint.setText(
                "Model replies, page verification, eligibility checks and saved "
                "lists are live; automatic search is still to come."
            )
        else:
            self.hint.setText(
                "Offline preview \u2014 replies are placeholder text with no model behind them."
            )

    @staticmethod
    def _elided_path(text: str) -> str:
        metrics = QFontMetrics(QFont("Consolas", 9))
        return metrics.elidedText(text, Qt.ElideMiddle, 340)


class _VoiceWorker(QThread):
    """On-device dictation capture, off the UI thread."""

    heard = Signal(str)
    failed = Signal(str)

    def run(self) -> None:
        listen_once(self.heard.emit, self.failed.emit)

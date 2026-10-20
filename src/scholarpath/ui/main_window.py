"""Main window: light dashboard shell for the Milestone 1 chat loop.

Layout follows the user-supplied dashboard reference: navy sidebar, top bar,
gradient welcome card, quick-action tiles, conversation column, academic
profile panel. Every value shown is real application state - the profile and
feature tiles are explicitly marked as not built yet.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QUrl, Signal
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
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from scholarpath.config import AppConfig, config_path
from scholarpath.ui import theme
from scholarpath.ui.chat_controller import ChatController, Turn

GLYPH_EDUCATION = "\uE7BE"
GLYPH_CHAT = "\uE8BD"
GLYPH_PERSON = "\uE77B"
GLYPH_STAR = "\uE734"
GLYPH_DOCUMENT = "\uE8A5"
GLYPH_SETTING = "\uE713"
GLYPH_SEND = "\uE724"
GLYPH_ATTACH = "\uE723"
GLYPH_GLOBE = "\uE774"
GLYPH_CHECK = "\uE73E"

ACTION_TILES = (
    ("Find Scholarships", "From your profile", "M4", GLYPH_STAR, "#FFF1E8", "#FF4500"),
    ("Check Eligibility", "For a programme", "M5", GLYPH_CHECK, "#EAF9F0", "#10B981"),
    ("Explore Countries", "Where to study?", "M4", GLYPH_GLOBE, "#EAF2FF", "#3B82F6"),
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

        color = "#FFFFFF" if active else "#9AA6BC"
        icon = glyph_label(glyph, 15, color, self)
        icon.setFixedWidth(18)
        row.addWidget(icon)

        label = QLabel(text, self)
        label.setObjectName("NavTextActive" if active else "NavText")
        row.addWidget(label)
        row.addStretch(1)

        if badge:
            tag = QLabel(badge, self)
            tag.setObjectName("NavBadge")
            row.addWidget(tag)


class ActionTile(QPushButton):
    """Quick-action tile. Coloured icon, title, subtitle and milestone badge."""

    def __init__(
        self,
        glyph: str,
        title: str,
        subtitle: str,
        badge: str,
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

        chat_item = NavButton(GLYPH_CHAT, "Chat Assistant", active=True, parent=side)
        column.addWidget(chat_item)

        inactive = (
            (GLYPH_PERSON, "My Profile", 3),
            (GLYPH_EDUCATION, "Scholarships", 4),
            (GLYPH_STAR, "Saved Opportunities", 6),
            (GLYPH_DOCUMENT, "Documents", 3),
        )
        for glyph, label, number in inactive:
            item = NavButton(glyph, label, badge="Soon", parent=side)
            item.setEnabled(False)
            item.setCursor(Qt.ArrowCursor)
            item.setToolTip(f"Coming in Milestone {number}. Not available in this build.")
            column.addWidget(item)

        settings = NavButton(GLYPH_SETTING, "Settings", parent=side)
        settings.setToolTip("Open the folder that holds config.toml")
        settings.clicked.connect(self._open_config_folder)
        column.addWidget(settings)

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
        body = QWidget(self)
        row = QHBoxLayout(body)
        row.setContentsMargins(24, 20, 24, 14)
        row.setSpacing(18)
        row.addWidget(self._build_chat_column(), 1)
        row.addWidget(self._build_right_panel())
        return body

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
            "I'm your scholarship assistant. This build can talk with you, but it "
            "cannot search or verify scholarships yet \u2014 research and eligibility "
            "arrive in later milestones.",
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
            tile = ActionTile(glyph, title_text, subtitle, "Soon", tint, accent, tiles)
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
        self.attach.setToolTip("Document upload arrives in Milestone 3")
        self.attach.setStyleSheet("font-family: 'Segoe MDL2 Assets'; font-size: 15px;")
        self.attach.clicked.connect(lambda: self._not_available("Document upload", "M3"))

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
        tag = QLabel("Soon", card)
        tag.setObjectName("CapSoon")
        tag.setToolTip("Profile setup arrives in Milestone 3.")
        header.addWidget(tag)
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
        name = QLabel("Not set up yet", card)
        name.setObjectName("ProfileName")
        detail = QLabel("Local profile \u00b7 Milestone 3", card)
        detail.setObjectName("ProfileSub")
        naming.addWidget(name)
        naming.addWidget(detail)
        identity.addLayout(naming, 1)
        column.addLayout(identity)

        track = QFrame(card)
        track.setObjectName("Track")
        track.setFixedHeight(6)
        column.addWidget(track)

        progress = QLabel("0% complete \u2014 no profile data yet", card)
        progress.setObjectName("TrackLabel")
        column.addWidget(progress)

        rows = (
            ("D", "Current degree", "\u2014"),
            ("G", "GPA", "\u2014"),
            ("I", "IELTS", "\u2014"),
            ("C", "Preferred countries", "\u2014"),
        )
        for letter, label_text, value_text in rows:
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
            row.addLayout(words, 1)
            column.addLayout(row)
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
            "ScholarPath will not invent profile details. Profile setup and "
            "document import arrive in Milestone 3.",
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
            ("Documents", "Soon", False, "Arrives in Milestone 3 - profile, upload, extraction."),
            ("Research", "Soon", False, "Arrives in Milestone 4 - source-verified discovery."),
            ("Eligibility", "Soon", False, "Arrives in Milestone 5 - deterministic checks."),
            ("Saved list", "Soon", False, "Arrives in Milestone 6 - comparison and bookmarks."),
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

    # -- wiring -----------------------------------------------------------
    def _connect(self) -> None:
        self.send_button.clicked.connect(self._submit)
        self.input.submitted.connect(self._submit)
        self.input.installEventFilter(self)
        self._controller.turn_added.connect(self._on_turn_added)
        self._controller.busy_changed.connect(self._on_busy_changed)
        self._controller.failed.connect(self._on_failed)

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
        widget = TurnWidget(turn, self.transcript.widget())
        self._turns_layout.insertWidget(self._turns_layout.count() - 1, widget)
        self.transcript.verticalScrollBar().setValue(
            self.transcript.verticalScrollBar().maximum()
        )
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
        elif live:
            self.subtitle.setText(
                "Model replies are live. Scholarship research is still to come."
            )
        else:
            self.subtitle.setText(
                "Offline preview \u2014 replies are placeholder text, no model behind them."
            )

        if live:
            self.hint.setText(
                "Model replies are live. Research, eligibility and documents are not built yet."
            )
        else:
            self.hint.setText(
                "Offline preview \u2014 replies are placeholder text with no model behind them."
            )

    @staticmethod
    def _elided_path(text: str) -> str:
        metrics = QFontMetrics(QFont("Consolas", 9))
        return metrics.elidedText(text, Qt.ElideMiddle, 340)

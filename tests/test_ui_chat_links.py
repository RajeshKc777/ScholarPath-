"""Chat replies carry clickable web addresses (G177).

The owner asked for the links in an answer to be clickable, not plain text.
The reply stays plain prose - no markdown is added - but every `http(s)`
address in it becomes a link that opens in the browser.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QLabel

from scholarpath.prose import LINK_COLOUR, USER_LINK_COLOUR
from scholarpath.ui.chat_controller import Turn
from scholarpath.ui.main_window import TurnWidget


def _body(widget: TurnWidget, name: str) -> QLabel:
    for label in widget.findChildren(QLabel):
        if label.objectName() == name:
            return label
    raise AssertionError(f"no {name} label in the turn widget")


def test_a_reply_renders_its_addresses_as_links() -> None:
    widget = TurnWidget(
        Turn(role="assistant", text="Check https://example.org/x for the deadline.")
    )
    body = _body(widget, "AsstBody")

    assert body.textFormat() == Qt.RichText
    assert body.openExternalLinks() is True
    assert '<a href="https://example.org/x"' in body.text()
    assert "https://example.org/x" in body.text()


def test_a_pasted_address_in_the_question_is_a_link_too() -> None:
    widget = TurnWidget(
        Turn(role="user", text="Is https://example.org/x still open?")
    )
    body = _body(widget, "UserBody")

    assert body.openExternalLinks() is True
    assert '<a href="https://example.org/x"' in body.text()


def test_a_reply_without_an_address_has_no_link() -> None:
    widget = TurnWidget(Turn(role="assistant", text="No address in this sentence."))
    body = _body(widget, "AsstBody")

    assert "<a href" not in body.text()


# -- G185: the link is a strong blue, not the faded shade Qt paints ------------


def test_the_anchor_carries_the_strong_blue_itself() -> None:
    widget = TurnWidget(
        Turn(role="assistant", text="Check https://example.org/x for the deadline.")
    )
    body = _body(widget, "AsstBody")

    assert f'color:{LINK_COLOUR}' in body.text()
    assert "text-decoration:underline" in body.text()


def test_the_link_colour_is_a_strong_blue() -> None:
    colour = QColor(LINK_COLOUR)

    assert colour.blue() > 150, "the blue channel is strong"
    assert colour.blue() > colour.red() + 60, "and it reads as blue, not grey"
    assert colour.value() < 230, "and it is not a washed-out tint"


def test_the_palette_link_colour_matches_the_anchor() -> None:
    widget = TurnWidget(
        Turn(role="assistant", text="Check https://example.org/x for the deadline.")
    )
    body = _body(widget, "AsstBody")

    assert body.palette().color(QPalette.Link).name().upper() == LINK_COLOUR


def test_a_link_on_the_orange_user_bubble_is_white() -> None:
    widget = TurnWidget(
        Turn(role="user", text="Is https://example.org/x still open?")
    )
    body = _body(widget, "UserBody")

    assert f'color:{USER_LINK_COLOUR}' in body.text()
    assert body.palette().color(QPalette.Link).name().upper() == USER_LINK_COLOUR

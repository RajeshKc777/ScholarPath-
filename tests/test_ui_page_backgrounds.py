"""Every page paints a light background (G173).

The scroll area's viewport and content widget are plain QWidgets. When Windows
runs in dark mode their unstyled background is the system window colour, which
is near-black, so the page shows black strips around its cards and dark text on
dark. The theme now sets those backgrounds; this test holds it by grabbing each
page off-screen and failing when a large share of the pixels is near-black.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import scholarpath.ui.main_window as main_window
from scholarpath.config import AppConfig, PrivacyConfig
from scholarpath.gateway.stub import StubGateway
from scholarpath.ui.chat_controller import ChatController
from scholarpath.ui.main_window import MainWindow

#: A pixel counts as near-black when every channel is below this. The theme's
#: text colour (#17202E) is below it too, but text is thin; a background bug
#: covers whole blocks, not single glyphs.
NEAR_BLACK = 48

#: Sampling stride: every fourth pixel in both directions.
STEP = 4

#: Small enough that a few dark text pixels pass, large enough that a black
#: strip or a black page body (the bug) fails.
MAX_DARK_SHARE = 0.01


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(app: QApplication, tmp_path_factory: pytest.TempPathFactory) -> MainWindow:
    home = tmp_path_factory.mktemp("page-backgrounds")
    current = main_window.database_path
    main_window.database_path = lambda: home / "pages.db"
    config = AppConfig(
        privacy=PrivacyConfig(voice_stt=False, voice_tts=False, web_search=False)
    )
    config.freshness.auto = False
    built = MainWindow(ChatController(StubGateway(), "stub"), config)
    built.setAttribute(Qt.WA_DontShowOnScreen, True)
    built.resize(1280, 792)
    built.show()
    QTest.qWait(100)
    try:
        yield built
    finally:
        built.close()
        main_window.database_path = current


def _dark_share(window: MainWindow) -> tuple[float, list[tuple[int, int, int]]]:
    """The share of near-black samples, and how dark the densest block is."""
    image = window.grab().toImage()
    total = 0
    dark = 0
    blocks: dict[tuple[int, int], list[int]] = {}
    for y in range(0, image.height(), STEP):
        for x in range(0, image.width(), STEP):
            colour = image.pixelColor(x, y)
            total += 1
            is_dark = (
                colour.red() < NEAR_BLACK
                and colour.green() < NEAR_BLACK
                and colour.blue() < NEAR_BLACK
            )
            block = blocks.setdefault((x // 80, y // 80), [0, 0])
            block[1] += 1
            if is_dark:
                dark += 1
                block[0] += 1
    worst = sorted(blocks.items(), key=lambda item: -(item[1][0] / item[1][1]))[:3]
    detail = [
        (key[0] * 80, key[1] * 80, round(100 * counts[0] / counts[1]))
        for key, counts in worst
    ]
    return dark / total, detail


PAGES = (
    "chat",
    "profile",
    "documents",
    "research",
    "eligibility",
    "catalog",
    "discover",
    "saved",
    "settings",
)


@pytest.mark.parametrize("page", PAGES)
def test_no_page_paints_a_large_near_black_area(window: MainWindow, page: str) -> None:
    window.select_page(page)
    QTest.qWait(50)

    share, blocks = _dark_share(window)

    assert share <= MAX_DARK_SHARE, (
        f"the {page} page is {share:.1%} near-black; darkest 80px blocks "
        f"(x, y, % dark): {blocks}"
    )

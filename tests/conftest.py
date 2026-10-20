"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from scholarpath.gateway.stub import StubGateway


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    """QObjects and QtGui (fonts, images) need a full GUI application instance;
    a bare QCoreApplication crash-fails the process on first font use."""
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def stub_gateway() -> StubGateway:
    return StubGateway()

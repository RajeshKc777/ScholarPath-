"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication

from scholarpath.gateway.stub import StubGateway


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    """QObject signals need an application instance to be available."""
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


@pytest.fixture
def stub_gateway() -> StubGateway:
    return StubGateway()

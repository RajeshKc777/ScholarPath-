"""Desktop user interface (PySide6)."""

__all__ = ["MainWindow"]


def __getattr__(name: str):  # lazy import keeps Qt out of non-UI test runs
    if name == "MainWindow":
        from scholarpath.ui.main_window import MainWindow

        return MainWindow
    raise AttributeError(name)

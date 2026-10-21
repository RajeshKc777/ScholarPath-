"""Application entry point: parse args, validate config, build gateway, show UI."""

from __future__ import annotations

import argparse
import functools
import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from scholarpath import __version__
from scholarpath.config import ConfigError, init_config, load_config
from scholarpath.gateway.base import GatewayError
from scholarpath.gateway.factory import build_gateway
from scholarpath.logging_setup import setup_logging
from scholarpath.ui.chat_controller import ChatController
from scholarpath.ui.main_window import MainWindow
from scholarpath.websearch import search

logger = logging.getLogger("scholarpath.app")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scholarpath",
        description="ScholarPath AI - scholarship discovery and academic guidance.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="path to config.toml (default: the per-user application folder)",
    )
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="write the configuration template and exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ScholarPath AI {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.init_config:
        try:
            written = init_config(args.config)
        except (ConfigError, OSError) as exc:
            print(f"Cannot create configuration: {exc}", file=sys.stderr)
            return 2
        print(f"Configuration template written to {written}")
        return 0

    app = QApplication.instance() or QApplication(
        [sys.argv[0] if sys.argv else "scholarpath"]
    )
    app.setApplicationName("ScholarPath AI")
    app.setApplicationVersion(__version__)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        QMessageBox.critical(None, "ScholarPath AI - configuration error", str(exc))
        return 2

    log_file = setup_logging(config.log_level)
    logger.info(
        "starting ScholarPath AI %s provider=%s", __version__, config.gateway.provider
    )
    logger.info("log file: %s", log_file)

    try:
        gateway = build_gateway(config.gateway)
    except GatewayError as exc:
        logger.error("gateway unavailable: %s", exc.message)
        QMessageBox.critical(None, "ScholarPath AI - gateway not available", exc.message)
        return 3

    controller = ChatController(
        gateway,
        model=config.gateway.model or None,
        search_enabled=config.privacy.web_search,
        searcher=functools.partial(
            search, trusted_domains=config.search.trusted_domains
        ),
    )
    window = MainWindow(controller, config)
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover - module entry
    raise SystemExit(main())

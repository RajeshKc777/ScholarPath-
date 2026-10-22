"""Read one page and propose its fields, off the UI thread (G186).

Both places that verify a page use this one worker: the Scholarship Pages
page and the chat bubble that offers "Verify this page". It fetches the page,
asks the model to propose the scholarship fields, and checks every proposed
value against the page text word for word. Nothing is invented and nothing is
saved here - the caller decides what to do with the draft.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

from scholarpath.gateway.base import ChatRequest, GatewayError, Message, ModelGateway
from scholarpath.research import (
    SCHOLARSHIP_FIELD_NAMES,
    build_scholarship_draft,
    build_scholarship_prompt,
    parse_model_json,
)
from scholarpath.sources import FetchError, fetch_page

logger = logging.getLogger("scholarpath.ui.verify_worker")


class VerifyWorker(QThread):
    """Fetch + gateway proposal, off the UI thread."""

    fetched = Signal(object, str)   # Page | None, error ("")
    drafted = Signal(object, str)   # ScholarshipDraft | None, error ("")

    def __init__(self, url: str, gateway: ModelGateway, model: str | None) -> None:
        super().__init__()
        self._url = url
        self._gateway = gateway
        self._model = model

    def run(self) -> None:
        try:
            page = fetch_page(self._url)
        except (FetchError, ValueError, OSError) as exc:
            logger.info("page fetch failed: %s", exc)
            self.fetched.emit(None, str(exc))
            return
        self.fetched.emit(page, "")

        request = ChatRequest(
            messages=[Message(role="user", content=build_scholarship_prompt(page))],
            model=self._model,
        )
        try:
            response = self._gateway.complete(request)
            proposed = parse_model_json(response.text, allowed=SCHOLARSHIP_FIELD_NAMES)
        except GatewayError as exc:
            logger.info("scholarship proposal failed: %s", exc.message)
            self.drafted.emit(None, exc.message)
            return
        except Exception:  # noqa: BLE001 - unexpected errors surface plainly
            logger.exception("scholarship extraction crashed")
            self.drafted.emit(None, "The extraction step failed unexpectedly.")
            return
        self.drafted.emit(build_scholarship_draft(page, proposed), "")

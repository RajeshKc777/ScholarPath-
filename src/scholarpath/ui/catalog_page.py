"""The Catalog page: read the official portals and store what they state.

The page runs the catalog in the background (a Qt thread-pool job) so the
window stays usable, shows what is happening, counts the errors, and can be
stopped. Nothing is invented: a field is stored only when the model copied it
from the page and the verbatim check confirmed it.
"""

from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from scholarpath.catalog import CatalogEvent, CatalogRunner, CatalogStats
from scholarpath.gateway.base import ModelGateway
from scholarpath.registry import RegistryError, Source, load_registry, user_registry_path
from scholarpath.storage import Database

logger = logging.getLogger("scholarpath.ui.catalog")

#: How many pages one portal may contribute to a run (the student can change it).
DEFAULT_MAX_PAGES = 5


class _JobSignals(QObject):
    progress = Signal(object)   # CatalogEvent
    finished = Signal(object)    # CatalogStats
    failed = Signal(str)         # error message


class CatalogJob(QRunnable):
    """The catalog run, off the UI thread."""

    def __init__(self, runner: CatalogRunner) -> None:
        super().__init__()
        self._runner = runner
        self._signals = _JobSignals()

    @property
    def signals(self) -> _JobSignals:
        return self._signals

    def run(self) -> None:
        # Report every step through the job's signal, so the UI thread sees
        # the progress while this thread does the work.
        self._runner.progress = self._signals.progress.emit
        try:
            stats = self._runner.run()
        except Exception as exc:  # noqa: BLE001 - the job must never crash the app
            logger.exception("the catalog run failed")
            self._signals.failed.emit(str(exc))
            return
        self._signals.finished.emit(stats)


class SourceRow(QWidget):
    """One portal in the registry, with the switch to crawl it."""

    def __init__(self, source: Source, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.source = source
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._check = QCheckBox(self)
        self._check.setChecked(source.enabled)
        self._check.setToolTip("Crawl this portal during the next run.")
        row.addWidget(self._check, 0, Qt.AlignTop)

        words = QVBoxLayout()
        words.setSpacing(1)
        name = QLabel(source.name, self)
        name.setObjectName("RowLabel")
        meta = QLabel(
            f"{source.country} - {source.trust_level} - {source.base_url}", self
        )
        meta.setObjectName("DocMeta")
        meta.setWordWrap(True)
        words.addWidget(name)
        words.addWidget(meta)
        row.addLayout(words, 1)

    @property
    def enabled(self) -> bool:
        return self._check.isChecked()


class RecordCard(QFrame):
    """One stored catalog record, with the page it came from."""

    def __init__(self, record: dict, sources: list[dict], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DocCard")
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 12, 14, 12)
        column.setSpacing(5)

        head = QHBoxLayout()
        title = QLabel(record.get("title") or record.get("page_title") or "(no title)", self)
        title.setObjectName("DocName")
        title.setWordWrap(True)
        head.addWidget(title, 1)
        provider = QLabel(record.get("provider") or record.get("provider_domain"), self)
        provider.setObjectName("DocMeta")
        head.addWidget(provider)
        column.addLayout(head)

        details: list[str] = []
        if record.get("level"):
            details.append(f"Level: {record['level']}")
        if record.get("countries"):
            details.append(f"Country: {record['countries']}")
        if record.get("funding_type"):
            details.append(f"Funding: {record['funding_type']}")
        if record.get("deadline_text"):
            details.append(f"Deadline (as written on the page): {record['deadline_text']}")
        if record.get("deadline_date"):
            details.append(f"Deadline date: {record['deadline_date']}")
        if record.get("amount_text"):
            details.append(f"Amount: {record['amount_text']}")
        if details:
            line = QLabel(" - ".join(details), self)
            line.setObjectName("DocMeta")
            line.setWordWrap(True)
            column.addWidget(line)

        conflicts = (record.get("data") or {}).get("conflicts") or {}
        if conflicts:
            names = ", ".join(sorted(conflicts))
            warn = QLabel(
                f"Two pages state different values for: {names}. The value that "
                "was verified first was kept - open the pages to see both.",
                self,
            )
            warn.setObjectName("DocMeta")
            warn.setWordWrap(True)
            column.addWidget(warn)

        foot = QHBoxLayout()
        pages = QLabel(f"{len(sources)} page(s) behind this record", self)
        pages.setObjectName("DocMeta")
        foot.addWidget(pages)
        foot.addStretch(1)
        for source in sources[:3]:
            link = QPushButton("Open page", self)
            link.setObjectName("LinkButton")
            link.setCursor(Qt.PointingHandCursor)
            link.setToolTip(source.get("source_url", ""))
            link.clicked.connect(
                lambda _checked=False, url=source.get("source_url", ""): self._open(url)
            )
            foot.addWidget(link)
        column.addLayout(foot)

    @staticmethod
    def _open(url: str) -> None:
        if url:
            QDesktopServices.openUrl(QUrl(url))


class CatalogPage(QWidget):
    """Pick the portals, run the catalog, watch it happen."""

    def __init__(
        self,
        database: Database,
        gateway: ModelGateway,
        model: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database = database
        self._gateway = gateway
        self._model = model
        self._job: CatalogJob | None = None
        self._cancel = threading.Event()
        self._rows: list[SourceRow] = []
        self._registry_error = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        header = QVBoxLayout()
        header.setSpacing(3)
        title = QLabel("Catalog of official portals", self)
        title.setObjectName("PageTitle2")
        lead = QLabel(
            "Read the official scholarship portals below and store what their "
            "pages state. Every portal is checked against its own robots.txt, "
            "asked at most once a second, and every value is verified "
            "word-for-word against the page before it is saved.",
            self,
        )
        lead.setObjectName("PageLead")
        lead.setWordWrap(True)
        header.addWidget(title)
        header.addWidget(lead)
        outer.addLayout(header)

        # -- the registry ---------------------------------------------------
        self._registry_note = QLabel("", self)
        self._registry_note.setObjectName("PageLead")
        self._registry_note.setWordWrap(True)
        outer.addWidget(self._registry_note)

        registry_box = QFrame(self)
        registry_box.setObjectName("DocCard")
        registry_layout = QVBoxLayout(registry_box)
        registry_layout.setContentsMargins(14, 12, 14, 12)
        registry_layout.setSpacing(6)

        registry_head = QHBoxLayout()
        registry_title = QLabel("Portals", registry_box)
        registry_title.setObjectName("DocName")
        registry_head.addWidget(registry_title, 1)
        self._registry_path = QLabel("", registry_box)
        self._registry_path.setObjectName("DocMeta")
        registry_head.addWidget(self._registry_path)
        edit = QPushButton("Edit registry", registry_box)
        edit.setObjectName("LinkButton")
        edit.setCursor(Qt.PointingHandCursor)
        edit.setToolTip(
            "Open your editable copy of the sources registry. It is a plain "
            "text file: add, remove or disable a portal there."
        )
        edit.clicked.connect(self._open_registry)
        registry_head.addWidget(edit)
        registry_layout.addLayout(registry_head)

        self._registry_list = QVBoxLayout()
        self._registry_list.setSpacing(4)
        registry_layout.addLayout(self._registry_list)
        outer.addWidget(registry_box)

        # -- the run --------------------------------------------------------
        actions = QHBoxLayout()
        self._run_button = QPushButton("Start catalog run", self)
        self._run_button.setObjectName("PrimaryButton")
        self._run_button.clicked.connect(self._start)
        actions.addWidget(self._run_button)

        self._cancel_button = QPushButton("Cancel", self)
        self._cancel_button.setObjectName("GhostButton")
        self._cancel_button.setEnabled(False)
        self._cancel_button.clicked.connect(self._cancel_run)
        actions.addWidget(self._cancel_button)

        self._pages_spin = QSpinBox(self)
        self._pages_spin.setRange(1, 20)
        self._pages_spin.setValue(DEFAULT_MAX_PAGES)
        self._pages_spin.setToolTip(
            "How many pages one portal may contribute to a run."
        )
        actions.addWidget(QLabel("Pages per portal:", self))
        actions.addWidget(self._pages_spin)
        actions.addStretch(1)
        outer.addLayout(actions)

        self._progress = QProgressBar(self)
        self._progress.setRange(0, 0)  # busy: the total is not known up front
        self._progress.setVisible(False)
        outer.addWidget(self._progress)

        self._status = QLabel("", self)
        self._status.setObjectName("PageLead")
        self._status.setWordWrap(True)
        outer.addWidget(self._status)

        self._errors = QPlainTextEdit(self)
        self._errors.setObjectName("SourcePreview")
        self._errors.setReadOnly(True)
        self._errors.setFixedHeight(90)
        self._errors.setVisible(False)
        outer.addWidget(self._errors)

        # -- what was stored -------------------------------------------------
        results_title = QLabel("Stored records", self)
        results_title.setObjectName("PageTitle2")
        outer.addWidget(results_title)

        scroll = QScrollArea(self)
        scroll.setObjectName("DocScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        holder.setObjectName("DocBody")
        self._records = QVBoxLayout(holder)
        self._records.setContentsMargins(0, 0, 0, 12)
        self._records.setSpacing(12)
        self._records.addStretch(1)
        scroll.setWidget(holder)
        outer.addWidget(scroll, 1)

        self.reload()

    # -- registry ----------------------------------------------------------
    def reload(self) -> None:
        """Re-read the registry and the stored records."""
        while self._registry_list.count():
            item = self._registry_list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._rows = []
        self._registry_error = ""

        try:
            sources = load_registry()
        except RegistryError as exc:
            self._registry_error = str(exc)
            self._run_button.setEnabled(False)
            self._registry_note.setText(
                f"The sources registry could not be read, so nothing can be "
                f"crawled: {exc}"
            )
            self._registry_path.setText(str(user_registry_path()))
        else:
            self._run_button.setEnabled(True)
            path = user_registry_path()
            self._registry_path.setText(str(path))
            self._registry_note.setText(
                f"{len(sources)} official portal(s) are listed. Only these sites "
                "are ever read, and only inside the paths each entry allows."
            )
            for source in sources:
                row = SourceRow(source, self)
                self._rows.append(row)
                self._registry_list.addWidget(row)

        self._reload_records()

    def _reload_records(self) -> None:
        while self._records.count() > 1:  # keep the trailing stretch
            item = self._records.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        records = list(self._database.catalog_records())
        if not records:
            placeholder = QLabel(
                "No catalog records yet. Start a run to read the official "
                "portals above.",
                self,
            )
            placeholder.setObjectName("PageLead")
            self._records.insertWidget(0, placeholder)
            return
        for record in records:
            sources = self._database.sources_for(int(record["id"]))
            self._records.insertWidget(
                self._records.count() - 1, RecordCard(record, sources, self)
            )

    def _open_registry(self) -> None:
        path = user_registry_path()
        if not path.exists():
            try:
                from scholarpath.registry import write_user_registry

                write_user_registry()
            except Exception:  # noqa: BLE001 - the button must not crash the app
                logger.exception("the editable registry could not be written")
                self._status.setText(
                    "The editable registry could not be created - the shipped "
                    "default is being used."
                )
                return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # -- the run -----------------------------------------------------------
    def _selected_sources(self) -> list[Source]:
        selected = []
        for row in self._rows:
            source = row.source
            if row.enabled:
                selected.append(
                    Source(
                        name=source.name,
                        base_url=source.base_url,
                        country=source.country,
                        trust_level=source.trust_level,
                        allowed_path_prefixes=source.allowed_path_prefixes,
                        crawl_depth=source.crawl_depth,
                        enabled=True,
                    )
                )
        return selected

    def _start(self) -> None:
        if self._job is not None:
            return
        sources = self._selected_sources()
        if not sources:
            self._status.setText("No portal is switched on - pick at least one.")
            return
        self._cancel.clear()
        self._errors.clear()
        self._errors.setVisible(False)
        self._run_button.setEnabled(False)
        self._cancel_button.setEnabled(True)
        self._progress.setVisible(True)
        self._status.setText("Starting the catalog run...")

        runner = CatalogRunner(
            self._database,
            self._gateway,
            self._model,
            sources=sources,
            max_pages=self._pages_spin.value(),
            cancel=self._cancel.is_set,
        )
        self._job = CatalogJob(runner)
        self._job.signals.progress.connect(self._on_progress_event)
        self._job.signals.finished.connect(self._on_finished)
        self._job.signals.failed.connect(self._on_failed)
        QThreadPool.globalInstance().start(self._job)

    def _cancel_run(self) -> None:
        self._cancel.set()
        self._status.setText("Stopping after the current page...")

    def _on_progress_event(self, event: CatalogEvent) -> None:
        if event.kind == "error":
            self._errors.appendPlainText(event.message)
            self._errors.setVisible(True)
        if event.kind == "source":
            self._status.setText(event.message)
        elif event.kind == "record":
            self._status.setText(event.message)
        elif event.kind == "done":
            self._status.setText(event.message)

    def _on_finished(self, stats: CatalogStats) -> None:
        self._job = None
        self._run_button.setEnabled(True)
        self._cancel_button.setEnabled(False)
        self._progress.setVisible(False)
        self._status.setText(stats.summary())
        self._reload_records()

    def _on_failed(self, message: str) -> None:
        self._job = None
        self._run_button.setEnabled(True)
        self._cancel_button.setEnabled(False)
        self._progress.setVisible(False)
        self._status.setText(f"The catalog run failed: {message}")

    def shutdown(self) -> None:
        """Stop a running job when the window closes."""
        self._cancel.set()

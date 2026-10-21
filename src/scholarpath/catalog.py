"""The catalog run: crawl -> fetch -> extract -> verify -> save.

One run walks the official portals in the sources registry, reads their
scholarship pages, and stores what those pages actually say.

The order matters, and every step keeps the honesty rules:

1. **Crawl** - the crawler finds pages (sitemap, feed, same-site links) and
   obeys robots.txt. It reads nothing outside the paths the registry allows.
2. **Extract** - the model is asked for the scholarship fields, exactly as on
   the Scholarships page.
3. **Verify** - every proposed value is checked word-for-word against the page
   text (`research.build_scholarship_draft`). A value the page does not state
   is never stored.
4. **Save** - the verified values are merged into the record they belong to
   (`storage.upsert_catalog_record`). A field that already holds a verified
   value is never overwritten; the difference is written down as a conflict.

The runner is deliberately free of Qt so it can be tested without a screen;
the Catalog page wraps it in a background job.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Iterable

from scholarpath.crawler import CrawlPage, CrawlResult, Crawler
from scholarpath.extraction import parse_model_json, single_date
from scholarpath.gateway.base import ChatRequest, GatewayError, Message, ModelGateway
from scholarpath.registry import Source, load_registry
from scholarpath.research import (
    SCHOLARSHIP_FIELD_NAMES,
    build_scholarship_draft,
    build_scholarship_prompt,
)
from scholarpath.storage import Database, catalog_field_values

logger = logging.getLogger("scholarpath.catalog")


@dataclass(frozen=True)
class CatalogEvent:
    """One thing that happened during a run, for the progress panel."""

    kind: str  # "source" | "page" | "record" | "error" | "done"
    source: str = ""
    message: str = ""
    pages: int = 0
    records: int = 0
    errors: int = 0


@dataclass
class CatalogStats:
    """The honest totals of a run."""

    sources: int = 0
    pages_read: int = 0
    pages_unchanged: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_merged: int = 0
    errors: int = 0
    skipped: int = 0
    cancelled: bool = False

    @property
    def records(self) -> int:
        return self.records_created + self.records_updated + self.records_merged

    def summary(self) -> str:
        parts = [
            f"{self.sources} portal(s)",
            f"{self.pages_read} page(s) read",
            f"{self.records} record(s) stored",
        ]
        if self.pages_unchanged:
            parts.append(f"{self.pages_unchanged} unchanged")
        if self.errors:
            parts.append(f"{self.errors} error(s)")
        if self.cancelled:
            parts.append("stopped early")
        return " - ".join(parts)


def catalog_values(verified: dict[str, str]) -> dict[str, str]:
    """The catalog fields, taken from the verified values and nothing else."""
    values: dict[str, str] = {
        "title": verified.get("title", ""),
        "institution": verified.get("institution", ""),
    }
    values.update(catalog_field_values(verified))
    return values


class CatalogRunner:
    """Runs the catalog for a set of official portals."""

    def __init__(
        self,
        database: Database,
        gateway: ModelGateway,
        model: str | None = None,
        sources: Iterable[Source] | None = None,
        crawler: Crawler | None = None,
        max_pages: int | None = None,
        cancel: Callable[[], bool] | None = None,
        progress: Callable[[CatalogEvent], None] | None = None,
    ) -> None:
        self._database = database
        self._gateway = gateway
        self._model = model
        self._sources = list(sources) if sources is not None else load_registry()
        self._crawler = crawler
        self._max_pages = max_pages
        self._cancel = cancel or (lambda: False)
        #: Where progress is reported. The Catalog page replaces this with a
        #: signal emitter, so the UI thread hears about every step.
        self.progress = progress or (lambda event: None)

    # -- helpers ----------------------------------------------------------
    def _emit(self, event: CatalogEvent) -> None:
        try:
            self.progress(event)
        except Exception:  # noqa: BLE001 - a broken listener must not stop the run
            logger.exception("the catalog progress listener failed")

    def _cancelled(self) -> bool:
        return bool(self._cancel())

    def _build_crawler(self) -> Crawler:
        if self._crawler is not None:
            return self._crawler
        kwargs: dict[str, object] = {
            "conditional": self._database.source_conditions(),
        }
        if self._max_pages is not None:
            kwargs["max_pages"] = self._max_pages
        return Crawler(**kwargs)  # type: ignore[arg-type]

    # -- the run ----------------------------------------------------------
    def run(self) -> CatalogStats:
        """Walk every enabled source and store what its pages state."""
        stats = CatalogStats()
        crawler = self._build_crawler()

        for source in self._sources:
            if self._cancelled():
                stats.cancelled = True
                break
            if not source.enabled:
                continue
            stats.sources += 1
            self._emit(
                CatalogEvent(kind="source", source=source.name, message=f"Reading {source.name}...")
            )
            result = self._crawl_source(crawler, source, stats)
            for page in result.pages:
                if self._cancelled():
                    stats.cancelled = True
                    break
                self._handle_page(page, source, stats)

        self._emit(
            CatalogEvent(
                kind="done",
                message=stats.summary(),
                pages=stats.pages_read,
                records=stats.records,
                errors=stats.errors,
            )
        )
        return stats

    def _crawl_source(
        self, crawler: Crawler, source: Source, stats: CatalogStats
    ) -> CrawlResult:
        try:
            result = crawler.crawl(source)
        except Exception as exc:  # noqa: BLE001 - one portal must not stop the run
            logger.exception("crawling %s failed", source.name)
            stats.errors += 1
            self._emit(
                CatalogEvent(
                    kind="error",
                    source=source.name,
                    message=f"{source.name}: {exc}",
                    errors=stats.errors,
                )
            )
            return CrawlResult(source_name=source.name)

        stats.pages_read += len(result.pages)
        stats.pages_unchanged += len(result.unchanged)
        stats.skipped += len(result.skipped)
        for problem in result.errors:
            stats.errors += 1
            self._emit(
                CatalogEvent(
                    kind="error",
                    source=source.name,
                    message=problem,
                    errors=stats.errors,
                )
            )
        return result

    def _handle_page(
        self, page: CrawlPage, source: Source, stats: CatalogStats
    ) -> None:
        """Extract, verify and store one page."""
        try:
            page_object = page.to_page()
            request = ChatRequest(
                messages=[Message(role="user", content=build_scholarship_prompt(page_object))],
                model=self._model,
            )
            response = self._gateway.complete(request)
            proposed = parse_model_json(
                response.text, allowed=SCHOLARSHIP_FIELD_NAMES, keep_unknown=True
            )
        except GatewayError as exc:
            stats.errors += 1
            self._emit(
                CatalogEvent(
                    kind="error",
                    source=source.name,
                    message=f"{page.url} - {exc.message}",
                    errors=stats.errors,
                )
            )
            return
        except Exception:  # noqa: BLE001 - a broken page must not stop the run
            logger.exception("extraction failed for %s", page.url)
            stats.errors += 1
            self._emit(
                CatalogEvent(
                    kind="error",
                    source=source.name,
                    message=f"{page.url} - the extraction step failed unexpectedly.",
                    errors=stats.errors,
                )
            )
            return

        draft = build_scholarship_draft(page_object, proposed)
        verified = draft.verified_values()
        if not verified:
            self._emit(
                CatalogEvent(
                    kind="page",
                    source=source.name,
                    message=f"{page.url} - no field could be verified on the page.",
                    pages=stats.pages_read,
                )
            )
            return

        values = dict(verified)
        try:
            record_id, action = self._database.upsert_catalog_record(
                values=values,
                unknown=draft.unknown_fields(),
                warnings=list(draft.warnings),
                source_url=page.url,
                final_url=page.final_url,
                retrieved_at=page.fetched_at,
                page_sha256=page.sha256,
                page_title=page.title,
                provider=source.name,
                provider_domain=source.domain,
                source_name=source.name,
                trust_level=source.trust_level,
                country=source.country,
                etag=page.etag,
                last_modified=page.last_modified,
            )
        except Exception:  # noqa: BLE001 - a storage problem must not stop the run
            logger.exception("storing %s failed", page.url)
            stats.errors += 1
            self._emit(
                CatalogEvent(
                    kind="error",
                    source=source.name,
                    message=f"{page.url} - the record could not be saved.",
                    errors=stats.errors,
                )
            )
            return

        if action == "created":
            stats.records_created += 1
        elif action == "updated":
            stats.records_updated += 1
        else:
            stats.records_merged += 1

        self._emit(
            CatalogEvent(
                kind="record",
                source=source.name,
                message=(
                    f"{values.get('title') or page.title or page.url} - "
                    f"record {record_id} ({action})"
                ),
                pages=stats.pages_read,
                records=stats.records,
                errors=stats.errors,
            )
        )

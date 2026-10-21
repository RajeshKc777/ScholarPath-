"""SQLite storage: the single local database used by profiles and documents.

Rules kept from goals.md (G110):
- The database lives in the per-user application folder, never inside the repo.
- One writer connection guarded by a lock; all access goes through this module.
- Documents may contain personal data, so log identifiers only, never content.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

from scholarpath.config import app_data_dir
from scholarpath.extraction import single_date

DB_FILENAME = "scholarpath.db"
_SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    mime TEXT NOT NULL,
    created_at TEXT NOT NULL,
    text TEXT NOT NULL,
    ocr_used INTEGER NOT NULL DEFAULT 0,
    warnings TEXT NOT NULL DEFAULT '[]',
    extraction TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS scholarship (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    institution TEXT NOT NULL DEFAULT '',
    requested_url TEXT NOT NULL,
    final_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    page_sha256 TEXT NOT NULL,
    page_title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'page-verified',
    data TEXT NOT NULL DEFAULT '{}'
);

-- Phase 1 (catalog): the structured fields of a scholarship record. Every one
-- of them holds the wording the official page used, or an empty string.
CREATE TABLE IF NOT EXISTS scholarship_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scholarship_id INTEGER NOT NULL,
    source_name TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT '',
    trust_level TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL,
    final_url TEXT NOT NULL DEFAULT '',
    retrieved_at TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL DEFAULT '',
    page_title TEXT NOT NULL DEFAULT '',
    etag TEXT NOT NULL DEFAULT '',
    last_modified TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE (scholarship_id, source_url)
);

CREATE TABLE IF NOT EXISTS saved_opportunity (
    scholarship_id INTEGER PRIMARY KEY CHECK (scholarship_id > 0),
    saved_at TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS checklist_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scholarship_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE (scholarship_id, text)
);
"""


def database_path(home: Path | None = None) -> Path:
    return (home or app_data_dir()) / DB_FILENAME


#: The catalog fields of a scholarship record, and the research field each one
#: is copied from. The value is always the wording of the official page.
CATALOG_FIELDS: dict[str, str] = {
    "level": "degree_levels",
    "countries": "host_country",
    "fields_of_study": "disciplines",
    "funding_type": "funding_coverage",
    "amount_text": "stipend",
    "deadline_text": "deadline",
    "language_req": "language_requirement",
    "apply_url": "application_url",
}

#: Columns added after the first release; older databases get them on open.
_MIGRATION_COLUMNS: dict[str, str] = {
    "provider": "TEXT NOT NULL DEFAULT ''",
    "provider_domain": "TEXT NOT NULL DEFAULT ''",
    "level": "TEXT NOT NULL DEFAULT ''",
    "countries": "TEXT NOT NULL DEFAULT ''",
    "fields_of_study": "TEXT NOT NULL DEFAULT ''",
    "funding_type": "TEXT NOT NULL DEFAULT ''",
    "amount_text": "TEXT NOT NULL DEFAULT ''",
    "deadline_text": "TEXT NOT NULL DEFAULT ''",
    "deadline_date": "TEXT",
    "language_req": "TEXT NOT NULL DEFAULT ''",
    "apply_url": "TEXT NOT NULL DEFAULT ''",
    "canonical_key": "TEXT NOT NULL DEFAULT ''",
}


def canonical_key(title: str, provider_domain: str, fallback: str = "") -> str:
    """The key a record is recognised by: its title and the portal it came from.

    The title is normalised (case, punctuation and spacing) so that the same
    scholarship written slightly differently on two pages is still one record.
    A page without a title falls back to its own address, so it is never
    merged into an unrelated record.
    """
    words = re.findall(r"\w+", (title or "").casefold())
    if words:
        return f"{provider_domain.casefold()}|{' '.join(words)}"
    return f"{provider_domain.casefold()}|url:{fallback.casefold()}"


def domain_of(url: str) -> str:
    """The registrable-looking host of a URL, without a leading 'www.'."""
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def catalog_field_values(values: dict[str, str]) -> dict[str, str]:
    """The catalog columns for a dict of research field values (verbatim only)."""
    return {name: values.get(source, "") for name, source in CATALOG_FIELDS.items()}


def catalog_columns(values: dict[str, str]) -> dict[str, str | None]:
    """The stored catalog columns for verified research values.

    The only place where research field names (``deadline``) are mapped onto
    catalog columns (``deadline_text``, ``deadline_date``). The date is parsed
    from the page's own wording, and stays empty when that wording is
    ambiguous or names more than one day.
    """
    columns: dict[str, str | None] = dict(catalog_field_values(values))
    parsed = single_date(values.get("deadline", ""))
    columns["deadline_date"] = parsed.isoformat() if parsed else None
    return columns


class Database:
    """Thread-safe wrapper over one SQLite connection."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(
            str(path), check_same_thread=False, isolation_level=None
        )
        self._connection.row_factory = sqlite3.Row
        with self._lock:
            # executescript manages its own transaction; do not wrap it in BEGIN.
            self._connection.executescript(_SCHEMA)
            self._migrate()

    def _migrate(self) -> None:
        """Give an older database the columns the catalog needs.

        A database created before the catalog existed has no `level`,
        `deadline_date` or `canonical_key` column; they are added here so the
        student's existing records are kept, not thrown away.
        """
        existing = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(scholarship)")
        }
        for column, definition in _MIGRATION_COLUMNS.items():
            if column in existing:
                continue
            self._connection.execute(
                f"ALTER TABLE scholarship ADD COLUMN {column} {definition}"
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    # -- transaction helpers ----------------------------------------------
    class _Write:
        def __init__(self, connection: sqlite3.Connection, lock: threading.Lock) -> None:
            self._connection = connection
            self._lock = lock

        def __enter__(self) -> sqlite3.Cursor:
            self._lock.acquire()
            self._connection.execute("BEGIN IMMEDIATE")
            return self._connection.cursor()

        def __exit__(self, exc_type, exc, tb) -> None:
            try:
                if exc_type is None:
                    self._connection.execute("COMMIT")
                else:
                    self._connection.execute("ROLLBACK")
            finally:
                self._lock.release()

    def _write(self) -> "Database._Write":
        return Database._Write(self._connection, self._lock)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    # -- profile -------------------------------------------------------------
    def load_profile(self) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT data, updated_at FROM profile WHERE id = 1"
            ).fetchone()
        if row is None:
            return None
        return {"data": json.loads(row["data"]), "updated_at": row["updated_at"]}

    def save_profile(self, data: dict[str, Any]) -> None:
        with self._write() as cursor:
            cursor.execute(
                "INSERT INTO profile (id, data, updated_at) VALUES (1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET data = excluded.data, "
                "updated_at = excluded.updated_at",
                (json.dumps(data, ensure_ascii=False, sort_keys=True), self._now()),
            )

    def clear_profile(self) -> None:
        with self._write() as cursor:
            cursor.execute("DELETE FROM profile WHERE id = 1")

    # -- documents -----------------------------------------------------------
    def add_document(
        self,
        filename: str,
        mime: str,
        text: str,
        ocr_used: bool,
        warnings: list[str],
    ) -> int:
        with self._write() as cursor:
            cursor.execute(
                "INSERT INTO document (filename, mime, created_at, text, ocr_used, "
                "warnings) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    filename,
                    mime,
                    self._now(),
                    text,
                    int(ocr_used),
                    json.dumps(warnings, ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)

    def save_extraction(self, document_id: int, extraction: dict[str, Any]) -> None:
        with self._write() as cursor:
            cursor.execute(
                "UPDATE document SET extraction = ? WHERE id = ?",
                (json.dumps(extraction, ensure_ascii=False), document_id),
            )

    def documents(self) -> Iterator[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, filename, mime, created_at, ocr_used, warnings, extraction "
                "FROM document ORDER BY id DESC"
            ).fetchall()
        for row in rows:
            yield dict(row) | {
                "warnings": json.loads(row["warnings"]),
                "extraction": json.loads(row["extraction"]),
            }

    def document_text(self, document_id: int) -> str:
        with self._lock:
            row = self._connection.execute(
                "SELECT text FROM document WHERE id = ?", (document_id,)
            ).fetchone()
        return row["text"] if row else ""

    def last_document_id(self) -> int | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT MAX(id) AS last FROM document"
            ).fetchone()
        return int(row["last"]) if row and row["last"] is not None else None

    # -- scholarships ------------------------------------------------------
    def save_scholarship(
        self,
        values: dict[str, str],
        unknown: list[str],
        requested_url: str,
        final_url: str,
        retrieved_at: str,
        page_sha256: str,
        page_title: str,
        warnings: list[str],
    ) -> int:
        """Persist a page-verified scholarship record (values only, verbatim).

        This is the "paste one page" flow. It fills the same catalog columns as
        a catalog run, so both flows share one record identity and a later
        catalog run merges into the record instead of duplicating it.
        """
        payload = {
            "values": dict(values),
            "unknown": list(unknown),
            "warnings": list(warnings),
        }
        title = values.get("title", "")[:200]
        institution = values.get("institution", "")[:200]
        columns = catalog_columns(values)
        domain = domain_of(final_url)
        key = canonical_key(title, domain, final_url)
        with self._write() as cursor:
            cursor.execute(
                "INSERT INTO scholarship (created_at, title, institution, "
                "requested_url, final_url, retrieved_at, page_sha256, page_title, "
                "status, data, provider, provider_domain, level, countries, "
                "fields_of_study, funding_type, amount_text, deadline_text, "
                "deadline_date, language_req, apply_url, canonical_key) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?, ?, ?)",
                (
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    title,
                    institution,
                    requested_url,
                    final_url,
                    retrieved_at,
                    page_sha256,
                    page_title,
                    "page-verified",
                    json.dumps(payload, ensure_ascii=False),
                    "",
                    domain,
                    (columns.get("level") or "")[:200],
                    (columns.get("countries") or "")[:200],
                    (columns.get("fields_of_study") or "")[:400],
                    (columns.get("funding_type") or "")[:200],
                    (columns.get("amount_text") or "")[:200],
                    (columns.get("deadline_text") or "")[:200],
                    columns.get("deadline_date"),
                    (columns.get("language_req") or "")[:200],
                    (columns.get("apply_url") or "")[:300],
                    key,
                ),
            )
            record_id = int(cursor.lastrowid)  # type: ignore[arg-type]
        self.add_source(
            record_id,
            source_url=requested_url,
            final_url=final_url,
            retrieved_at=retrieved_at,
            sha256=page_sha256,
            page_title=page_title,
            source_name="Page you pasted",
        )
        return record_id

    def scholarships(self) -> Iterator[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, created_at, title, institution, requested_url, "
                "final_url, retrieved_at, page_sha256, page_title, status, data "
                "FROM scholarship ORDER BY id"
            ).fetchall()
        for row in rows:
            item = dict(row)
            item["data"] = json.loads(row["data"])
            yield item

    # -- catalog (Phase 1) -------------------------------------------------
    def catalog_records(self) -> Iterator[dict[str, Any]]:
        """Every record with its catalog fields and the pages it came from."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, created_at, title, institution, provider, "
                "provider_domain, level, countries, fields_of_study, "
                "funding_type, amount_text, deadline_text, deadline_date, "
                "language_req, apply_url, canonical_key, requested_url, "
                "final_url, retrieved_at, page_sha256, page_title, status, data "
                "FROM scholarship ORDER BY id"
            ).fetchall()
        for row in rows:
            item = dict(row)
            item["data"] = json.loads(row["data"])
            yield item

    def find_by_canonical_key(self, key: str) -> dict[str, Any] | None:
        """The record with this key, or None."""
        if not key:
            return None
        with self._lock:
            row = self._connection.execute(
                "SELECT id, title, data, canonical_key FROM scholarship "
                "WHERE canonical_key = ? ORDER BY id LIMIT 1",
                (key,),
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["data"] = json.loads(row["data"])
        return item

    def upsert_catalog_record(
        self,
        *,
        values: dict[str, str],
        unknown: list[str],
        warnings: list[str],
        source_url: str,
        final_url: str,
        retrieved_at: str,
        page_sha256: str,
        page_title: str,
        provider: str,
        provider_domain: str,
        source_name: str = "",
        trust_level: str = "",
        country: str = "",
        etag: str = "",
        last_modified: str = "",
    ) -> tuple[int, str]:
        """Store one verified page, merging it into the record it belongs to.

        `values` are the verified research values (the names the Scholarships
        page uses, e.g. ``deadline``); the catalog columns are derived from
        them here, so there is exactly one mapping.

        A record is recognised by its ``canonical_key`` (the normalised title
        and the portal's domain). When the record already exists:

        - a field that is still empty is filled in;
        - a field that already holds a verified value is **never overwritten** -
          the difference is written down as a conflict instead, so nothing is
          changed behind the student's back;
        - the page is added to the record's source list.

        Returns (scholarship id, what happened): ``created``, ``updated`` or
        ``merged``.
        """
        key = canonical_key(values.get("title", ""), provider_domain, source_url)
        existing = self.find_by_canonical_key(key)
        columns = catalog_columns(values)

        if existing is None:
            record_id = self._insert_catalog_record(
                values=values,
                columns=columns,
                unknown=list(unknown),
                warnings=list(warnings),
                source_url=source_url,
                final_url=final_url,
                retrieved_at=retrieved_at,
                page_sha256=page_sha256,
                page_title=page_title,
                provider=provider,
                provider_domain=provider_domain,
                key=key,
            )
            self.add_source(
                record_id,
                source_url=source_url,
                final_url=final_url,
                retrieved_at=retrieved_at,
                sha256=page_sha256,
                page_title=page_title,
                source_name=source_name,
                provider=provider,
                trust_level=trust_level,
                country=country,
                etag=etag,
                last_modified=last_modified,
            )
            return record_id, "created"

        data = existing.get("data") or {}
        old_values = dict(data.get("values") or {})
        conflicts = dict(data.get("conflicts") or {})
        changed = False

        for name, new_value in values.items():
            if not new_value:
                continue
            old_value = old_values.get(name, "")
            if not old_value:
                old_values[name] = new_value
                changed = True
            elif old_value != new_value:
                # The page says something different: keep what was verified
                # before and write the difference down.
                conflicts.setdefault(name, []).append(
                    {"kept": old_value, "ignored": new_value, "source": source_url}
                )

        merged_unknown = sorted(set(data.get("unknown") or []) | set(unknown))
        merged_warnings = sorted(set(data.get("warnings") or []) | set(warnings))
        payload = {
            "values": old_values,
            "unknown": merged_unknown,
            "warnings": merged_warnings,
        }
        if conflicts:
            payload["conflicts"] = conflicts

        self._update_catalog_record(
            record_id=int(existing["id"]),
            values=old_values,
            columns=catalog_columns(old_values),
            payload=payload,
            final_url=final_url,
            retrieved_at=retrieved_at,
            page_sha256=page_sha256,
            page_title=page_title,
            provider=provider,
            provider_domain=provider_domain,
            key=key,
        )
        added = self.add_source(
            int(existing["id"]),
            source_url=source_url,
            final_url=final_url,
            retrieved_at=retrieved_at,
            sha256=page_sha256,
            page_title=page_title,
            source_name=source_name,
            provider=provider,
            trust_level=trust_level,
            country=country,
            etag=etag,
            last_modified=last_modified,
        )
        if not added:
            return int(existing["id"]), "merged"
        return int(existing["id"]), "updated" if changed else "merged"

    def _insert_catalog_record(
        self,
        *,
        values: dict[str, str],
        columns: dict[str, str | None],
        unknown: list[str],
        warnings: list[str],
        source_url: str,
        final_url: str,
        retrieved_at: str,
        page_sha256: str,
        page_title: str,
        provider: str,
        provider_domain: str,
        key: str,
    ) -> int:
        payload = {
            "values": dict(values),
            "unknown": list(unknown),
            "warnings": list(warnings),
        }
        with self._write() as cursor:
            cursor.execute(
                "INSERT INTO scholarship (created_at, title, institution, "
                "requested_url, final_url, retrieved_at, page_sha256, "
                "page_title, status, data, provider, provider_domain, level, "
                "countries, fields_of_study, funding_type, amount_text, "
                "deadline_text, deadline_date, language_req, apply_url, "
                "canonical_key) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?, ?)",
                (
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    values.get("title", "")[:200],
                    values.get("institution", "")[:200],
                    source_url,
                    final_url,
                    retrieved_at,
                    page_sha256,
                    page_title[:200],
                    "page-verified",
                    json.dumps(payload, ensure_ascii=False),
                    provider[:120],
                    provider_domain[:120],
                    (columns.get("level") or "")[:200],
                    (columns.get("countries") or "")[:200],
                    (columns.get("fields_of_study") or "")[:400],
                    (columns.get("funding_type") or "")[:200],
                    (columns.get("amount_text") or "")[:200],
                    (columns.get("deadline_text") or "")[:200],
                    columns.get("deadline_date"),
                    (columns.get("language_req") or "")[:200],
                    (columns.get("apply_url") or "")[:300],
                    key,
                ),
            )
            return int(cursor.lastrowid)  # type: ignore[arg-type]

    def _update_catalog_record(
        self,
        *,
        record_id: int,
        values: dict[str, str],
        columns: dict[str, str | None],
        payload: dict[str, Any],
        final_url: str,
        retrieved_at: str,
        page_sha256: str,
        page_title: str,
        provider: str,
        provider_domain: str,
        key: str,
    ) -> None:
        with self._write() as cursor:
            cursor.execute(
                "UPDATE scholarship SET title = ?, institution = ?, "
                "final_url = ?, retrieved_at = ?, page_sha256 = ?, "
                "page_title = ?, data = ?, provider = ?, provider_domain = ?, "
                "level = ?, countries = ?, fields_of_study = ?, funding_type = ?, "
                "amount_text = ?, deadline_text = ?, deadline_date = ?, "
                "language_req = ?, apply_url = ?, canonical_key = ? WHERE id = ?",
                (
                    values.get("title", "")[:200],
                    values.get("institution", "")[:200],
                    final_url,
                    retrieved_at,
                    page_sha256,
                    page_title[:200],
                    json.dumps(payload, ensure_ascii=False),
                    provider[:120],
                    provider_domain[:120],
                    (columns.get("level") or "")[:200],
                    (columns.get("countries") or "")[:200],
                    (columns.get("fields_of_study") or "")[:400],
                    (columns.get("funding_type") or "")[:200],
                    (columns.get("amount_text") or "")[:200],
                    (columns.get("deadline_text") or "")[:200],
                    columns.get("deadline_date"),
                    (columns.get("language_req") or "")[:200],
                    (columns.get("apply_url") or "")[:300],
                    key,
                    record_id,
                ),
            )

    def add_source(
        self,
        scholarship_id: int,
        *,
        source_url: str,
        final_url: str = "",
        retrieved_at: str = "",
        sha256: str = "",
        page_title: str = "",
        source_name: str = "",
        provider: str = "",
        trust_level: str = "",
        country: str = "",
        etag: str = "",
        last_modified: str = "",
    ) -> bool:
        """Record one official page behind a scholarship. False when known."""
        with self._write() as cursor:
            cursor.execute(
                "INSERT INTO scholarship_sources (scholarship_id, source_name, "
                "provider, trust_level, country, source_url, final_url, "
                "retrieved_at, sha256, page_title, etag, last_modified, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(scholarship_id, source_url) DO NOTHING",
                (
                    scholarship_id,
                    source_name[:120],
                    provider[:120],
                    trust_level[:40],
                    country[:80],
                    source_url,
                    final_url,
                    retrieved_at,
                    sha256,
                    page_title[:200],
                    etag[:200],
                    last_modified[:200],
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )
            return cursor.rowcount > 0

    def sources_for(self, scholarship_id: int) -> list[dict[str, Any]]:
        """The official pages behind one record."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, scholarship_id, source_name, provider, trust_level, "
                "country, source_url, final_url, retrieved_at, sha256, "
                "page_title, etag, last_modified, created_at "
                "FROM scholarship_sources WHERE scholarship_id = ? ORDER BY id",
                (scholarship_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def source_conditions(self) -> dict[str, tuple[str, str]]:
        """Every known page with its ETag / Last-Modified, for a conditional run."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT source_url, etag, last_modified FROM scholarship_sources "
                "WHERE etag != '' OR last_modified != ''"
            ).fetchall()
        return {
            row["source_url"]: (row["etag"], row["last_modified"]) for row in rows
        }

    def delete_scholarship(self, scholarship_id: int) -> bool:
        with self._write() as cursor:
            cursor.execute(
                "DELETE FROM saved_opportunity WHERE scholarship_id = ?",
                (scholarship_id,),
            )
            cursor.execute(
                "DELETE FROM checklist_item WHERE scholarship_id = ?",
                (scholarship_id,),
            )
            cursor.execute(
                "DELETE FROM scholarship_sources WHERE scholarship_id = ?",
                (scholarship_id,),
            )
            cursor.execute("DELETE FROM scholarship WHERE id = ?", (scholarship_id,))
            return cursor.rowcount > 0

    # -- saved opportunities -------------------------------------------------
    def save_opportunity(self, scholarship_id: int, note: str = "") -> None:
        """Bookmark a verified record. Idempotent; re-saving refreshes note."""
        with self._write() as cursor:
            cursor.execute(
                "INSERT INTO saved_opportunity (scholarship_id, saved_at, note) "
                "VALUES (?, ?, ?) ON CONFLICT(scholarship_id) DO UPDATE SET "
                "note = excluded.note, saved_at = excluded.saved_at",
                (
                    scholarship_id,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    note[:500],
                ),
            )

    def unsave_opportunity(self, scholarship_id: int) -> bool:
        with self._write() as cursor:
            cursor.execute(
                "DELETE FROM saved_opportunity WHERE scholarship_id = ?",
                (scholarship_id,),
            )
            return cursor.rowcount > 0

    def is_saved(self, scholarship_id: int) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM saved_opportunity WHERE scholarship_id = ?",
                (scholarship_id,),
            ).fetchone()
        return row is not None

    def saved_opportunity_ids(self) -> list[int]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT scholarship_id FROM saved_opportunity ORDER BY saved_at DESC"
            ).fetchall()
        return [int(row["scholarship_id"]) for row in rows]

    def counts(self) -> dict[str, int]:
        """Cheap counters for the Settings page (no document bodies read)."""
        with self._lock:
            documents = self._connection.execute(
                "SELECT COUNT(*) AS n FROM document"
            ).fetchone()["n"]
            scholarships = self._connection.execute(
                "SELECT COUNT(*) AS n FROM scholarship"
            ).fetchone()["n"]
            saved = self._connection.execute(
                "SELECT COUNT(*) AS n FROM saved_opportunity"
            ).fetchone()["n"]
        return {"documents": int(documents), "scholarships": int(scholarships), "saved": int(saved)}

    # -- application checklists ----------------------------------------------
    def replace_checklist(
        self, scholarship_id: int, items: list[str]
    ) -> None:
        """Replace the generated draft items, keeping ticks for surviving texts."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._lock:
            previous = {
                row["text"]: row["done"]
                for row in self._connection.execute(
                    "SELECT text, done FROM checklist_item WHERE scholarship_id = ?",
                    (scholarship_id,),
                ).fetchall()
            }
        with self._write() as cursor:
            cursor.execute(
                "DELETE FROM checklist_item WHERE scholarship_id = ?",
                (scholarship_id,),
            )
            for text in items:
                done = previous.get(text, 0)
                cursor.execute(
                    "INSERT INTO checklist_item "
                    "(scholarship_id, text, done, created_at) VALUES (?, ?, ?, ?)",
                    (scholarship_id, text[:300], done, now),
                )

    def checklist_items(self, scholarship_id: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, text, done, created_at FROM checklist_item "
                "WHERE scholarship_id = ? ORDER BY id",
                (scholarship_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_checklist_done(self, item_id: int, done: bool) -> None:
        with self._write() as cursor:
            cursor.execute(
                "UPDATE checklist_item SET done = ? WHERE id = ?",
                (1 if done else 0, item_id),
            )

    def delete_document(self, document_id: int) -> None:
        with self._write() as cursor:
            cursor.execute("DELETE FROM document WHERE id = ?", (document_id,))

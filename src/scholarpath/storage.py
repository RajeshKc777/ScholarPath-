"""SQLite storage: the single local database used by profiles and documents.

Rules kept from goals.md (G110):
- The database lives in the per-user application folder, never inside the repo.
- One writer connection guarded by a lock; all access goes through this module.
- Documents may contain personal data, so log identifiers only, never content.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from scholarpath.config import app_data_dir

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
        """Persist a page-verified scholarship record (values only, verbatim)."""
        payload = {
            "values": dict(values),
            "unknown": list(unknown),
            "warnings": list(warnings),
        }
        title = values.get("title", "")[:200]
        institution = values.get("institution", "")[:200]
        with self._write() as cursor:
            cursor.execute(
                "INSERT INTO scholarship (created_at, title, institution, "
                "requested_url, final_url, retrieved_at, page_sha256, page_title, "
                "status, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                ),
            )
            return int(cursor.lastrowid)  # type: ignore[arg-type]

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

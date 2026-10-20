"""M3 storage and ingestion: local database, profile merge, document parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from scholarpath.documents import extract_text, ocr_available
from scholarpath.profiles import Profile, merge_confirmed
from scholarpath.storage import Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.db")
    yield database
    database.close()


# -- database -------------------------------------------------------------------
def test_profile_round_trip(db: Database) -> None:
    assert db.load_profile() is None
    db.save_profile({"gpa": "3.62", "ielts": "6.5"})
    loaded = db.load_profile()
    assert loaded is not None
    assert loaded["data"] == {"gpa": "3.62", "ielts": "6.5"}
    assert loaded["updated_at"]
    db.save_profile({"gpa": "3.70"})
    assert db.load_profile()["data"] == {"gpa": "3.70"}
    db.clear_profile()
    assert db.load_profile() is None


def test_documents_round_trip(db: Database) -> None:
    doc_id = db.add_document("marksheet.png", "image/png", "OCR text here", True, ["note"])
    rows = list(db.documents())
    assert len(rows) == 1
    assert rows[0]["filename"] == "marksheet.png"
    assert rows[0]["ocr_used"] == 1
    assert rows[0]["warnings"] == ["note"]
    assert db.document_text(doc_id) == "OCR text here"
    db.save_extraction(doc_id, {"gpa": "3.62"})
    assert list(db.documents())[0]["extraction"] == {"gpa": "3.62"}
    db.delete_document(doc_id)
    assert list(db.documents()) == []


def test_database_creates_parent_directories(tmp_path: Path) -> None:
    nested = Database(tmp_path / "a" / "b" / "scholarpath.db")
    nested.save_profile({"gpa": "4"})
    assert nested.load_profile()["data"] == {"gpa": "4"}
    nested.close()


# -- profile model ---------------------------------------------------------------
def test_profile_completion_counts_only_filled_fields() -> None:
    empty = Profile()
    assert empty.completion() == 0
    assert empty.filled_fields() == []

    some = Profile(gpa="3.62", ielts="6.5", updated_at="x")
    assert some.filled_fields() == ["gpa", "ielts"]
    assert 0 < some.completion() < 100


def test_profile_payload_drops_bookkeeping() -> None:
    profile = Profile(gpa="3.62", updated_at="ts")
    assert "updated_at" not in profile.as_payload()


def test_profile_from_payload_keeps_good_fields_and_reports_dropped() -> None:
    profile, dropped = Profile.from_payload({"gpa": "3.62", "toefl": 105, "ghost": "x"})
    assert profile.gpa == "3.62"
    assert "toefl" in dropped          # wrong type
    assert "ghost" not in dropped      # unknown names are simply ignored


def test_merge_confirmed_applies_only_confirmed_values() -> None:
    base = Profile(gpa="3.50")
    merged = merge_confirmed(base, {"gpa": "3.62", "ielts": "6.5", "bogus": "x", "toefl": None})
    assert merged.gpa == "3.62"
    assert merged.ielts == "6.5"
    assert merged.toefl == ""
    assert not hasattr(merged, "bogus")
    assert merged.updated_at  # stamped on every merge


def test_merge_confirmed_never_wipes_with_none() -> None:
    base = Profile(ielts="7.0")
    merged = merge_confirmed(base, {"ielts": None})
    assert merged.ielts == "7.0"


# -- document ingestion -------------------------------------------------------------
def test_text_file_extraction(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("Student: Ram\nGPA: 3.62", encoding="utf-8")
    doc = extract_text(path)
    assert doc.mime == "text/plain"
    assert "GPA: 3.62" in doc.text
    assert not doc.ocr_used
    assert doc.warnings == []


def test_non_utf8_text_uses_fallback_with_warning(tmp_path: Path) -> None:
    path = tmp_path / "legacy.txt"
    path.write_bytes("GPA: 3,62 Sch\u00fcler".encode("cp1252"))  # 0xFC is invalid UTF-8
    doc = extract_text(path)
    assert doc.text.startswith("GPA")
    assert any("UTF-8" in warning for warning in doc.warnings)


def test_pdf_text_layer_extraction(tmp_path: Path) -> None:
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    content = DecodedStreamObject()
    content.set_data(
        b"BT /F1 18 Tf 72 720 Td (GPA: 3.62 / 4.00) Tj ET\n"
        b"BT /F1 18 Tf 72 690 Td (Student: Ram Bahadur Thapa) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(content)  # noqa: SLF001 - pypdf API
    font = writer._add_object(  # noqa: SLF001
        __import__("pypdf.generic", fromlist=["DictionaryObject"]).DictionaryObject()
    )
    font.update(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = __import__(
        "pypdf.generic", fromlist=["DictionaryObject"]
    ).DictionaryObject()
    page["/Resources"][NameObject("/Font")] = __import__(
        "pypdf.generic", fromlist=["DictionaryObject"]
    ).DictionaryObject({NameObject("/F1"): font})
    target = tmp_path / "doc.pdf"
    with target.open("wb") as handle:
        writer.write(handle)

    doc = extract_text(target)
    assert doc.mime == "application/pdf"
    assert "GPA: 3.62 / 4.00" in doc.text
    assert "Ram Bahadur Thapa" in doc.text
    assert doc.warnings == []


def test_scanned_pdf_without_text_layer_says_so(tmp_path: Path) -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    target = tmp_path / "scan.pdf"
    with target.open("wb") as handle:
        writer.write(handle)

    doc = extract_text(target)
    assert doc.empty
    assert any("scan" in warning for warning in doc.warnings)


def test_unsupported_type_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "archive.zip"
    path.write_bytes(b"PK\x03\x04")
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text(path)


def test_oversize_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "big.txt"
    path.write_bytes(b"x" * (26 * 1024 * 1024))
    with pytest.raises(ValueError, match="too large"):
        extract_text(path)


def test_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        extract_text(tmp_path / "nope.txt")


# -- OCR (Windows-only; skipped when no engine is installed) -------------------------
needs_ocr = pytest.mark.skipif(not ocr_available(), reason="no Windows OCR engine")


@needs_ocr
def test_image_ocr_reads_rendered_text(tmp_path: Path) -> None:
    from PySide6.QtGui import QColor, QFont, QImage, QPainter
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    image = QImage(1800, 400, QImage.Format_RGB32)
    image.fill(QColor("#FFFFFF"))
    painter = QPainter(image)
    painter.setPen(QColor("#111111"))
    painter.setFont(QFont("Arial", 38))
    painter.drawText(60, 120, "Student: Ram Bahadur Thapa")
    painter.drawText(60, 240, "GPA: 3.62 / 4.00")
    painter.end()
    target = tmp_path / "marksheet.png"
    assert image.save(str(target))

    doc = extract_text(target)
    assert doc.ocr_used
    assert "Ram Bahadur Thapa" in doc.text
    assert "3.62" in doc.text

    draft_source = doc.text
    from scholarpath.extraction import build_draft

    verified = build_draft("marksheet.png", draft_source, {"student_name": "Ram Bahadur Thapa"})
    assert verified.fields[0].verified

# -- M6: saved opportunities + checklists ----------------------------------------

def _seed(database: Database, title: str = "Grant A") -> int:
    return database.save_scholarship(
        values={"title": title},
        unknown=[],
        requested_url="https://example.edu/a",
        final_url="https://example.edu/a",
        retrieved_at="2026-10-20T10:00:00",
        page_sha256="abc",
        page_title=title,
        warnings=[],
    )


def test_save_unsave_round_trip(db: Database) -> None:
    assert db.is_saved(1) is False
    assert db.saved_opportunity_ids() == []
    sid = _seed(db)
    db.save_opportunity(sid, note="fallback choice")
    assert db.is_saved(sid) is True
    assert db.saved_opportunity_ids() == [sid]
    db.unsave_opportunity(sid)
    assert db.is_saved(sid) is False


def test_re_saving_replaces_note(db: Database) -> None:
    sid = _seed(db)
    db.save_opportunity(sid, note="first")
    db.save_opportunity(sid, note="second")
    ids = db.saved_opportunity_ids()
    assert ids == [sid]
    assert db.is_saved(sid)


def test_delete_scholarship_cascades_to_saved_and_checklist(db: Database) -> None:
    sid = _seed(db)
    db.save_opportunity(sid)
    db.replace_checklist(sid, ["Passport copy"])
    items = db.checklist_items(sid)
    assert len(items) == 1
    assert db.delete_scholarship(sid) is True
    assert db.is_saved(sid) is False
    assert db.checklist_items(sid) == []


def test_checklist_round_trip_and_tick_survival(db: Database) -> None:
    sid = _seed(db)
    db.replace_checklist(sid, ["Passport copy", "Transcript"])
    items = db.checklist_items(sid)
    assert [item["text"] for item in items] == ["Passport copy", "Transcript"]
    assert all(item["done"] == 0 for item in items)
    db.set_checklist_done(items[0]["id"], True)
    # Re-generate with one surviving and one new item: the tick must survive.
    db.replace_checklist(sid, ["Passport copy", "Reference letter"])
    items = db.checklist_items(sid)
    ticks = {item["text"]: item["done"] for item in items}
    assert ticks == {"Passport copy": 1, "Reference letter": 0}


def test_checklist_isolated_between_records(db: Database) -> None:
    first = _seed(db)
    second = _seed(db, "Grant B")
    db.replace_checklist(first, ["A item"])
    db.replace_checklist(second, ["B item"])
    assert [item["text"] for item in db.checklist_items(first)] == ["A item"]
    assert [item["text"] for item in db.checklist_items(second)] == ["B item"]

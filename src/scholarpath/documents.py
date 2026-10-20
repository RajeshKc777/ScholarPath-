"""Document ingestion: turn a local file into text, honestly.

- PDF with a text layer  -> pypdf, page by page.
- Image (png/jpg/jpeg/bmp) -> Windows OCR (winsdk), run on a worker thread by
  the caller. Availability is probed lazily and cached.
- Plain text             -> read as UTF-8 with a latin-1 fallback.

What this never does: invent text that is not in the file. A scanned PDF has
no rasteriser in this build, so it stays unread and says so.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("scholarpath.documents")

MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_RECOGNIZED_CHARS = 400_000
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp"}

OCR_UNAVAILABLE = (
    "OCR is not available on this machine (no Windows OCR engine/language pack). "
    "Install English (United States) language support in Windows settings, then retry."
)


@dataclass(frozen=True, slots=True)
class DocumentText:
    """Extracted content plus honest provenance."""

    filename: str
    mime: str
    text: str
    ocr_used: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.text.strip()


_engine_cache: bool | None = None


def ocr_available(force_refresh: bool = False) -> bool:
    """True when Windows OCR works here. Import of winsdk is harmless alongside
    Qt provided a QApplication exists (verified 2026-10-20)."""
    global _engine_cache
    if _engine_cache is None or force_refresh:
        try:
            from winsdk.windows.media.ocr import OcrEngine

            _engine_cache = OcrEngine.try_create_from_user_profile_languages() is not None
        except Exception:  # noqa: BLE001 - not Windows / stack missing
            _engine_cache = False
        logger.info("windows ocr available=%s", _engine_cache)
    return _engine_cache


async def _recognize(image: Path) -> str:
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.storage import FileAccessMode, StorageFile

    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        raise RuntimeError("No Windows OCR engine is installed for this user.")
    file = await StorageFile.get_file_from_path_async(str(image))
    stream = await file.open_async(FileAccessMode.READ)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    result = await engine.recognize_async(bitmap)
    return result.text or ""


def _read_text_file(path: Path) -> tuple[str, list[str]]:
    warnings: list[str] = []
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
        warnings.append("File is not UTF-8; decoded with a legacy fallback.")
    text = text.replace("\x00", "")
    return text, warnings


def _read_pdf(path: Path) -> tuple[str, list[str]]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(page for page in pages if page.strip())
    warnings: list[str] = []
    if not text.strip():
        warnings.append(
            "This PDF has no text layer (it is a scan). This build cannot read "
            "scanned PDFs yet - export the pages as images and try again."
        )
    return text, warnings


def extract_text(path: Path) -> DocumentText:
    """Produce DocumentText. Raises ValueError for unsupported/unusable files."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"File not found: {path.name}")
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ValueError(
            f"File is too large ({size // (1024 * 1024)} MB, limit 25 MB)."
        )

    suffix = path.suffix.lower()
    filename = path.name

    if suffix in (".txt", ".md"):
        text, warnings = _read_text_file(path)
        return DocumentText(filename=filename, mime="text/plain", text=text, warnings=warnings)

    if suffix == ".pdf":
        text, warnings = _read_pdf(path)
        return DocumentText(
            filename=filename, mime="application/pdf", text=text, warnings=warnings
        )

    if suffix in IMAGE_SUFFIXES:
        if not ocr_available():
            return DocumentText(
                filename=filename,
                mime="image/" + suffix.lstrip("."),
                text="",
                warnings=[OCR_UNAVAILABLE],
            )
        text = asyncio.run(_recognize(path))
        warnings: list[str] = []
        if not text.strip():
            warnings.append("OCR ran but found no readable text in this image.")
        if len(text) > MAX_RECOGNIZED_CHARS:
            text = text[:MAX_RECOGNIZED_CHARS]
            warnings.append("Recognized text was truncated at 400,000 characters.")
        return DocumentText(
            filename=filename, mime="image/" + suffix.lstrip("."), text=text,
            ocr_used=True, warnings=warnings,
        )

    raise ValueError(
        f"Unsupported file type {filename!r}. This build reads .pdf, .txt, .md "
        "and image files."
    )

"""A minimal PDF with a real text layer, built in memory.

The suite must never touch the network, so the crawler tests serve this
document from the loopback fake server. pypdf can both write and read it, and
the text is extractable exactly as a real brochure's would be.
"""

from __future__ import annotations

from io import BytesIO


def make_pdf(text: str, *, blank: bool = False) -> bytes:
    """Return PDF bytes whose text layer is `text` (or none when blank)."""
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    if not blank:
        content = DecodedStreamObject()
        lines = "".join(
            f"BT /F1 16 Tf 72 {700 - index * 24} Td ({line}) Tj ET\n"
            for index, line in enumerate(text.splitlines())
        )
        content.set_data(lines.encode("latin-1", errors="replace"))
        page[NameObject("/Contents")] = writer._add_object(content)  # noqa: SLF001

        font = DictionaryObject()
        font.update(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject()
        page["/Resources"][NameObject("/Font")] = DictionaryObject(
            {NameObject("/F1"): writer._add_object(font)}  # noqa: SLF001
        )

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()

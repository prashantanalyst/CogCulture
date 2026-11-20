from __future__ import annotations
import io
import re
from dataclasses import dataclass
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from . import config


class PDFError(Exception):
    """User-facing PDF problem (message is safe to display)."""


@dataclass
class Document:
    pages: list            # [(page_number, text)]
    total_pages: int
    truncated: bool

    @property
    def text_chars(self):
        return sum(len(t) for _, t in self.pages)


def _clean(t: str) -> str:
    t = t.replace("\x00", " ")
    t = re.sub(r"-\n(?=[a-z])", "", t)          # re-join hyphenated line breaks
    t = re.sub(r"[ \t\u00a0]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def read_pdf(data: bytes) -> Document:
    if not data:
        raise PDFError("The file is empty.")
    if len(data) > config.MAX_PDF_MB * 1024 * 1024:
        raise PDFError(f"File is larger than {config.MAX_PDF_MB} MB.")
    if not data.lstrip()[:1024].startswith(b"%PDF"):
        raise PDFError("This does not look like a PDF file.")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                ok = reader.decrypt("")
            except Exception:
                ok = 0
            if not ok:
                raise PDFError("The PDF is password protected. Remove the password and try again.")
        total = len(reader.pages)
        if total == 0:
            raise PDFError("The PDF has no pages.")
        pages = []
        for i, page in enumerate(reader.pages[: config.MAX_PAGES], start=1):
            try:
                text = _clean(page.extract_text() or "")
            except Exception:
                text = ""
            pages.append((i, text))
    except PDFError:
        raise
    except (PyPdfError, ValueError, KeyError, OSError, RecursionError) as e:
        raise PDFError(f"Could not read this PDF ({type(e).__name__}). It may be corrupted.") from e
    return Document(pages=pages, total_pages=total, truncated=total > config.MAX_PAGES)

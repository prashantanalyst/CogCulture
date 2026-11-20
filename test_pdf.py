import pytest
from pypdf import PdfWriter
import io
from factcheck import config
from factcheck.pdf_extract import read_pdf, PDFError
from .helpers import make_pdf


def test_reads_text_and_page_numbers():
    d = read_pdf(make_pdf(["Hello world 42", "Second page 99%"]))
    assert d.total_pages == 2 and not d.truncated
    assert d.pages[0][0] == 1 and "Hello world 42" in d.pages[0][1]
    assert "99%" in d.pages[1][1]


def test_empty_bytes():
    with pytest.raises(PDFError, match="empty"):
        read_pdf(b"")


def test_not_a_pdf():
    with pytest.raises(PDFError, match="PDF"):
        read_pdf(b"hello, i am a text file")


def test_corrupted_pdf():
    with pytest.raises(PDFError):
        read_pdf(b"%PDF-1.7\n1 0 obj\n<< garbage >>\nendobj\n")


def test_truncated_pdf_does_not_crash():
    good = make_pdf(["abc " * 20])
    with pytest.raises(PDFError):
        read_pdf(good[: len(good) // 3])


def test_password_protected():
    w = PdfWriter()
    w.add_blank_page(200, 200)
    w.encrypt("secret")
    buf = io.BytesIO(); w.write(buf)
    with pytest.raises(PDFError, match="password"):
        read_pdf(buf.getvalue())


def test_too_large(monkeypatch):
    monkeypatch.setattr(config, "MAX_PDF_MB", 0)
    with pytest.raises(PDFError, match="larger"):
        read_pdf(make_pdf(["x"]))


def test_page_cap_sets_truncated(monkeypatch):
    monkeypatch.setattr(config, "MAX_PAGES", 2)
    d = read_pdf(make_pdf(["a one", "b two", "c three", "d four"]))
    assert d.total_pages == 4 and len(d.pages) == 2 and d.truncated


def test_image_only_or_blank_has_no_text():
    d = read_pdf(make_pdf(["", ""]))
    assert d.text_chars < config.MIN_TEXT_CHARS


def test_unicode_survives():
    d = read_pdf(make_pdf(["Revenue 100 euro 50%"]))
    assert "Revenue" in d.pages[0][1]

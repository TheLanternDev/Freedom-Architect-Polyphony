"""Test `POST /attachment/extract` — ekstrakcja tekstu z plików.

Pokrywa wszystkie 5 ścieżek: txt (passthrough), pdf, docx, oversize (413),
empty (400), unsupported ext (415), truncation przy >MAX_TEXT_CHARS.
"""

from __future__ import annotations

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.attachment import router as att_router, MAX_FILE_BYTES, MAX_TEXT_CHARS


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(att_router)
    return TestClient(app)


def _upload(tc, name: str, content: bytes, content_type: str = "application/octet-stream"):
    return tc.post(
        "/attachment/extract",
        files={"file": (name, content, content_type)},
    )


def test_extract_plain_text_passthrough(client):
    text = "To jest brief w pliku txt.\nDruga linia."
    r = _upload(client, "brief.txt", text.encode("utf-8"), "text/plain")
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == text.strip()
    assert body["chars"] == len(text.strip())
    assert body["truncated"] is False
    assert body["filename"] == "brief.txt"


def test_extract_markdown_is_supported(client):
    r = _upload(client, "notes.md", b"# Tytul\n\nTrescParagrafu.", "text/markdown")
    assert r.status_code == 200
    assert "Tytul" in r.json()["text"]


def test_extract_rejects_empty_file(client):
    r = _upload(client, "empty.txt", b"")
    assert r.status_code == 400


def test_extract_rejects_oversize_file(client):
    huge = b"x" * (MAX_FILE_BYTES + 1)
    r = _upload(client, "big.txt", huge)
    assert r.status_code == 413


def test_extract_rejects_unsupported_extension(client):
    r = _upload(client, "evil.exe", b"binary stuff")
    assert r.status_code == 415


def test_extract_handles_no_extension(client):
    r = _upload(client, "no_ext_file", b"content")
    assert r.status_code == 415


def test_extract_truncates_long_text(client):
    huge_text = ("A" * (MAX_TEXT_CHARS + 1000)).encode("utf-8")
    r = _upload(client, "long.txt", huge_text)
    assert r.status_code == 200
    body = r.json()
    assert body["truncated"] is True
    assert body["chars"] == MAX_TEXT_CHARS


def test_extract_non_utf8_text_is_replaced_not_crashed(client):
    """Plik nie-UTF8 nie crashuje — `errors='replace'`."""
    r = _upload(client, "latin.txt", b"caf\xe9 et th\xe9")
    assert r.status_code == 200
    # Nie sprawdzamy konkretnej wartości replacement chars, tylko brak crashu + chars > 0.
    assert r.json()["chars"] > 0


def test_extract_pdf_via_pypdf(client):
    """Inline generujemy 1-stronicowy PDF przez pypdf — bez zewnętrznego pliku."""
    try:
        from pypdf import PdfWriter
        from pypdf.generic import NameObject, TextStringObject
    except ImportError:
        pytest.skip("pypdf not installed in test env")

    # Minimalny prawidłowy PDF (1 strona, bez tekstu).
    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    w.write(buf)
    pdf_bytes = buf.getvalue()

    r = _upload(client, "blank.pdf", pdf_bytes, "application/pdf")
    # Pusta strona = pusty/empty text po extract → nadal 200 OK z chars=0.
    assert r.status_code == 200


def test_extract_docx_invalid_returns_422(client):
    """Plik z .docx ale niezgodny z formatem ZIP → 422 (nie 500)."""
    r = _upload(client, "fake.docx", b"this is not a real docx")
    assert r.status_code == 422

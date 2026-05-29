"""Załączniki: ekstrakcja tekstu z PDF/DOCX/tekstu do extra_context briefu.

Wzorzec spójny z voice.py (UploadFile + limit rozmiaru). Backend nie przechowuje
pliku — zwraca wyłącznie wyekstrahowany tekst (AKSJOMAT: brak ukrytego stanu).
"""
from __future__ import annotations

import io
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attachment", tags=["attachment"])

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
# Górny limit zwracanego tekstu = limit Brief.extra_context.
MAX_TEXT_CHARS = 8000

_TEXT_EXTS = {"txt", "md", "csv", "json", "log", "text"}


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise HTTPException(500, "pip install pypdf — wymagane dla PDF.")
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Nie udało się odczytać PDF: {e}") from e


def _extract_docx(data: bytes) -> str:
    try:
        import docx  # python-docx
    except ImportError:
        raise HTTPException(500, "pip install python-docx — wymagane dla DOCX.")
    try:
        document = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in document.paragraphs)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Nie udało się odczytać DOCX: {e}") from e


def _extract_text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


@router.post("/extract")
async def extract_attachment(file: UploadFile = File(...)) -> dict:
    """Zwraca wyekstrahowany tekst z pliku (PDF/DOCX/tekst), przycięty do limitu."""
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, f"Plik za duży (max {MAX_FILE_BYTES // 1024 // 1024} MB).")
    if not data:
        raise HTTPException(400, "Pusty plik.")

    ext = _ext(file.filename or "")
    if ext == "pdf":
        text = _extract_pdf(data)
    elif ext == "docx":
        text = _extract_docx(data)
    elif ext in _TEXT_EXTS:
        text = _extract_text(data)
    else:
        raise HTTPException(415, f"Nieobsługiwany typ: .{ext or '?'}")

    text = text.strip()
    truncated = len(text) > MAX_TEXT_CHARS
    if truncated:
        text = text[:MAX_TEXT_CHARS]

    return {"text": text, "chars": len(text), "truncated": truncated, "filename": file.filename}

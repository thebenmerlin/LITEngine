"""Extract plain text from an uploaded case document (.txt, .docx, .pdf)."""

import io
from typing import Set

from docx import Document as DocxDocument
from fastapi import HTTPException
from pypdf import PdfReader

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB
SUPPORTED_EXTENSIONS: Set[str] = {".txt", ".docx", ".pdf"}


def _suffix(filename: str) -> str:
    name = (filename or "").lower()
    for ext in SUPPORTED_EXTENSIONS:
        if name.endswith(ext):
            return ext
    return ""


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=422, detail="Could not decode text file — unrecognized encoding")


def _extract_docx(content: bytes) -> str:
    try:
        doc = DocxDocument(io.BytesIO(content))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read .docx file: {exc}") from exc
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read PDF file: {exc}") from exc
    if reader.is_encrypted:
        raise HTTPException(status_code=422, detail="This PDF is password-protected — remove the password and try again")
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def extract_text(filename: str, content: bytes) -> str:
    """Return plain text from an uploaded case document, or raise a
    user-facing HTTPException (400/422) describing what went wrong."""
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit")

    suffix = _suffix(filename)
    if not suffix:
        raise HTTPException(status_code=400, detail="Unsupported file type — use .txt, .docx, or .pdf")

    if suffix == ".txt":
        text = _decode_text(content)
    elif suffix == ".docx":
        text = _extract_docx(content)
    else:
        text = _extract_pdf(content)

    text = text.strip()
    if not text:
        raise HTTPException(
            status_code=422,
            detail="No extractable text found in this file — it may be a scanned or image-only document",
        )
    return text

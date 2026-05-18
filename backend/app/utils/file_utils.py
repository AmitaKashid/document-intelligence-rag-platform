import re
import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings


def sanitize_filename(filename: str) -> str:
    """
    Keep filenames safe for local storage.
    Example:
    'My Report (Final).pdf' -> 'My_Report_Final.pdf'
    """
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", filename.strip())
    cleaned = cleaned.strip("._")

    if not cleaned:
        cleaned = "uploaded_document.pdf"

    return cleaned


def validate_pdf_file(file: UploadFile) -> None:
    if not file.filename:
        raise ValueError("Missing filename.")

    suffix = Path(file.filename).suffix.lower()

    if suffix not in settings.ALLOWED_EXTENSIONS:
        raise ValueError("Only PDF files are supported.")

    if file.content_type and file.content_type not in settings.ALLOWED_CONTENT_TYPES:
        raise ValueError(
            f"Invalid content type '{file.content_type}'. Only PDF uploads are supported."
        )


def save_upload_file(file: UploadFile) -> dict:
    validate_pdf_file(file)

    document_id = str(uuid.uuid4())
    safe_filename = sanitize_filename(file.filename)

    stored_filename = f"{document_id}_{safe_filename}"
    stored_path = settings.UPLOAD_DIR / stored_filename

    with stored_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    size_bytes = stored_path.stat().st_size
    max_size_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    if size_bytes == 0:
        stored_path.unlink(missing_ok=True)
        raise ValueError("Uploaded file is empty.")

    if size_bytes > max_size_bytes:
        stored_path.unlink(missing_ok=True)
        raise ValueError(
            f"File exceeds maximum upload size of {settings.MAX_UPLOAD_SIZE_MB} MB."
        )

    return {
        "document_id": document_id,
        "original_filename": file.filename,
        "stored_filename": stored_filename,
        "stored_path": str(stored_path),
        "content_type": file.content_type,
        "size_bytes": size_bytes,
        "status": "uploaded",
    }
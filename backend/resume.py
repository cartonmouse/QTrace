from __future__ import annotations

import uuid
from pathlib import Path

from .document_import import (
    DocumentImportError,
    MAX_PDF_BYTES,
    extract_pdf_text_from_bytes,
)

MAX_RESUME_BYTES = MAX_PDF_BYTES
MAX_RESUME_TEXT_CHARS = 20_000


class ResumeError(ValueError):
    """Raised when an uploaded resume is invalid or cannot be read."""


def _resume_directory(user_id: str, data_dir: str | Path) -> Path:
    if not user_id or Path(user_id).name != user_id or user_id in {".", ".."}:
        raise ResumeError("用户目录无效")
    return Path(data_dir) / "users" / user_id / "resume"


def _resume_files(user_id: str, data_dir: str | Path) -> list[Path]:
    directory = _resume_directory(user_id, data_dir)
    if not directory.exists():
        return []
    return sorted(path for path in directory.glob("*.pdf") if path.is_file())


def get_resume_file(user_id: str, data_dir: str | Path) -> Path | None:
    files = _resume_files(user_id, data_dir)
    return files[0] if files else None


def extract_pdf_text(path: str | Path) -> str:
    """Extract text locally; the resume is passed directly to the provider, not embedded."""
    try:
        content = Path(path).read_bytes()
        return extract_pdf_text_from_bytes(
            Path(path).name,
            content,
            max_chars=MAX_RESUME_TEXT_CHARS,
            truncation_marker="简历文本已截断",
        )
    except DocumentImportError as exc:
        raise ResumeError(str(exc)) from exc
    except OSError as exc:
        raise ResumeError("PDF 无法读取") from exc


def get_resume_text(user_id: str, data_dir: str | Path) -> tuple[str, str]:
    path = get_resume_file(user_id, data_dir)
    if not path:
        return "", ""
    return extract_pdf_text(path), path.name


def get_resume_status(user_id: str, data_dir: str | Path) -> dict[str, object]:
    path = get_resume_file(user_id, data_dir)
    if not path:
        return {"has_resume": False, "filename": "", "size": 0, "text_chars": 0}
    text, _ = get_resume_text(user_id, data_dir)
    return {"has_resume": True, "filename": path.name, "size": path.stat().st_size, "text_chars": len(text)}


def save_resume(user_id: str, filename: str | None, content: bytes, data_dir: str | Path) -> dict[str, object]:
    try:
        text = extract_pdf_text_from_bytes(
            filename,
            content,
            max_chars=MAX_RESUME_TEXT_CHARS,
            truncation_marker="简历文本已截断",
        )
    except DocumentImportError as exc:
        raise ResumeError(str(exc)) from exc

    directory = _resume_directory(user_id, data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    temp_path = directory / f".upload-{uuid.uuid4().hex}.tmp"
    final_path = directory / filename
    temp_path.write_bytes(content)
    try:
        # The bytes were parsed before replacing the old file, so a malformed upload cannot destroy it.
        temp_path.replace(final_path)
        for old_path in _resume_files(user_id, data_dir):
            if old_path != final_path:
                old_path.unlink()
    except ResumeError:
        temp_path.unlink(missing_ok=True)
        raise
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        raise ResumeError("保存 PDF 失败") from exc

    return {
        "has_resume": True,
        "filename": final_path.name,
        "size": final_path.stat().st_size,
        "text_chars": len(text),
    }


def delete_resume(user_id: str, data_dir: str | Path) -> bool:
    deleted = False
    for path in _resume_files(user_id, data_dir):
        path.unlink()
        deleted = True
    return deleted

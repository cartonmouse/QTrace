from __future__ import annotations

import re
import uuid
from pathlib import Path


MAX_RESUME_BYTES = 20 * 1024 * 1024
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
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency installation issue
        raise ResumeError("缺少 pypdf 依赖，请先安装 backend/requirements.txt") from exc

    try:
        reader = PdfReader(str(path))
        raw_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:  # pypdf exposes several parser-specific exception types.
        raise ResumeError("PDF 无法解析，请确认文件未损坏") from exc

    text = re.sub(r"\n{3,}", "\n\n", raw_text).strip()
    if len(text) > MAX_RESUME_TEXT_CHARS:
        text = text[:MAX_RESUME_TEXT_CHARS].rstrip() + "\n[简历文本已截断]"
    return text


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
    if not filename:
        raise ResumeError("请选择 PDF 文件")
    if "/" in filename or "\\" in filename or Path(filename).name != filename:
        raise ResumeError("文件名不能包含路径")
    if not filename.lower().endswith(".pdf"):
        raise ResumeError("目前只支持 PDF 简历")
    if not content:
        raise ResumeError("文件内容为空")
    if len(content) > MAX_RESUME_BYTES:
        raise ResumeError("PDF 文件不能超过 20 MB")
    if b"%PDF-" not in content[:1024]:
        raise ResumeError("文件不是有效的 PDF")

    directory = _resume_directory(user_id, data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    temp_path = directory / f".upload-{uuid.uuid4().hex}.tmp"
    final_path = directory / filename
    temp_path.write_bytes(content)
    try:
        # Parse before replacing the old file, so a malformed upload does not destroy it.
        text = extract_pdf_text(temp_path)
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

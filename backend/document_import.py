from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re


MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_MARKDOWN_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_TEXT_CHARS = 100_000


class DocumentImportError(ValueError):
    """Raised when a local document upload cannot be validated or parsed."""


def _validate_pdf_upload(filename: str | None, content: bytes) -> None:
    if not filename:
        raise DocumentImportError("请选择 PDF 文件")
    if "/" in filename or "\\" in filename or Path(filename).name != filename:
        raise DocumentImportError("文件名不能包含路径")
    if not filename.lower().endswith(".pdf"):
        raise DocumentImportError("目前只支持 PDF 文件")
    if not content:
        raise DocumentImportError("文件内容为空")
    if len(content) > MAX_PDF_BYTES:
        raise DocumentImportError("PDF 文件不能超过 20 MB")
    if b"%PDF-" not in content[:1024]:
        raise DocumentImportError("文件不是有效的 PDF")


def _validate_markdown_upload(filename: str | None, content: bytes) -> None:
    if not filename:
        raise DocumentImportError("请选择 Markdown 文件")
    if "/" in filename or "\\" in filename or Path(filename).name != filename:
        raise DocumentImportError("文件名不能包含路径")
    if not filename.lower().endswith((".md", ".markdown")):
        raise DocumentImportError("目前只支持 Markdown（.md 或 .markdown）文件")
    if not content:
        raise DocumentImportError("Markdown 文件内容为空")
    if len(content) > MAX_MARKDOWN_BYTES:
        raise DocumentImportError("Markdown 文件不能超过 20 MB")


def _truncate_text(text: str, max_chars: int, truncation_marker: str) -> str:
    if len(text) <= max_chars:
        return text
    suffix = f"\n[{truncation_marker}]"
    keep_chars = max(0, max_chars - len(suffix))
    return text[:keep_chars].rstrip() + suffix


def _extract_pdf_text(
    content: bytes,
    *,
    max_chars: int,
    truncation_marker: str,
) -> str:
    if max_chars <= 0:
        raise DocumentImportError("文本长度上限必须大于 0")
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency installation issue
        raise DocumentImportError("缺少 pypdf 依赖，请先安装 backend/requirements.txt") from exc

    try:
        reader = PdfReader(BytesIO(content))
        raw_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:  # pypdf exposes several parser-specific exception types.
        raise DocumentImportError("PDF 无法解析，请确认文件未损坏") from exc

    text = re.sub(r"\n{3,}", "\n\n", raw_text).strip()
    return _truncate_text(text, max_chars, truncation_marker)


def extract_pdf_text_from_bytes(
    filename: str | None,
    content: bytes,
    *,
    max_chars: int = DEFAULT_MAX_TEXT_CHARS,
    truncation_marker: str = "文档文本已截断",
) -> str:
    """Validate and extract a text layer from a PDF without persisting the upload."""
    _validate_pdf_upload(filename, content)
    return _extract_pdf_text(
        content,
        max_chars=max_chars,
        truncation_marker=truncation_marker,
    )


def extract_markdown_text_from_bytes(
    filename: str | None,
    content: bytes,
    *,
    max_chars: int = DEFAULT_MAX_TEXT_CHARS,
    truncation_marker: str = "文档文本已截断",
) -> str:
    """Validate and decode a UTF-8 Markdown upload without persisting the file."""
    if max_chars <= 0:
        raise DocumentImportError("文本长度上限必须大于 0")
    _validate_markdown_upload(filename, content)
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentImportError("Markdown 文件必须使用 UTF-8 编码") from exc
    text = re.sub(r"\n{3,}", "\n\n", text.replace("\r\n", "\n").replace("\r", "\n")).strip()
    return _truncate_text(text, max_chars, truncation_marker)

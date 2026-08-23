from fastapi.testclient import TestClient

from backend.document_import import (
    DocumentImportError,
    extract_markdown_text_from_bytes,
    extract_pdf_text_from_bytes,
)
from backend.main import create_app


def _text_pdf(text: str) -> bytes:
    """Build a tiny text PDF without adding a test-only PDF generation dependency."""
    safe_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 20 200 Td ({safe_text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{number} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"
    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    pdf += b"".join(f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets[1:])
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    return pdf


def _register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password-123", "name": "PDF Learner"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_shared_pdf_importer_extracts_text_and_validates_filename():
    content = _text_pdf("QTrace personal memory")
    assert "QTrace personal memory" in extract_pdf_text_from_bytes("notes.pdf", content)

    try:
        extract_pdf_text_from_bytes("notes.txt", content)
    except DocumentImportError as exc:
        assert "PDF" in str(exc)
    else:  # pragma: no cover - assertion makes the expected exception explicit
        raise AssertionError("non-PDF filename should be rejected")


def test_markdown_importer_decodes_utf8_and_rejects_other_extensions():
    content = "# QTrace\n\n本地 Embedding 检索证据。".encode("utf-8")
    assert "本地 Embedding 检索证据" in extract_markdown_text_from_bytes("notes.md", content)
    assert extract_markdown_text_from_bytes("notes.markdown", b"\xef\xbb\xbf# Title").startswith("# Title")

    try:
        extract_markdown_text_from_bytes("notes.txt", content)
    except DocumentImportError as exc:
        assert "Markdown" in str(exc)
    else:  # pragma: no cover - assertion makes the expected exception explicit
        raise AssertionError("non-Markdown filename should be rejected")

    try:
        extract_markdown_text_from_bytes("notes.md", b"\xff\xfe")
    except DocumentImportError as exc:
        assert "UTF-8" in str(exc)
    else:  # pragma: no cover - assertion makes the expected exception explicit
        raise AssertionError("invalid UTF-8 should be rejected")


def test_pdf_upload_enters_personal_document_memory_and_is_searchable(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    headers = _register(client, "pdf-memory@example.test")
    response = client.post(
        "/api/agent/documents/upload",
        headers=headers,
        files={"file": ("qtrace-architecture.pdf", _text_pdf("QTrace local embedding project architecture evidence"), "application/pdf")},
    )
    assert response.status_code == 200
    document = response.json()
    assert document["title"] == "qtrace-architecture"
    assert document["source_type"] == "pdf"
    assert document["chunk_count"] == 1

    found = client.get(
        "/api/agent/documents/search",
        headers=headers,
        params={"q": "project architecture evidence"},
    )
    assert found.status_code == 200
    assert found.json()[0]["document_id"] == document["id"]


def test_markdown_upload_enters_personal_document_memory_and_is_searchable(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    headers = _register(client, "markdown-memory@example.test")
    response = client.post(
        "/api/agent/documents/upload",
        headers=headers,
        files={"file": ("qtrace-notes.md", "# QTrace\n\nMarkdown Agent evidence".encode("utf-8"), "text/markdown")},
    )
    assert response.status_code == 200
    document = response.json()
    assert document["title"] == "qtrace-notes"
    assert document["source_type"] == "markdown"
    assert document["chunk_count"] == 1

    found = client.get(
        "/api/agent/documents/search",
        headers=headers,
        params={"q": "Markdown Agent evidence"},
    )
    assert found.status_code == 200
    assert found.json()[0]["document_id"] == document["id"]


def test_pdf_upload_rejects_a_pdf_without_text_layer(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    headers = _register(client, "pdf-empty@example.test")
    empty_pdf = _text_pdf("")
    response = client.post(
        "/api/agent/documents/upload",
        headers=headers,
        files={"file": ("scan.pdf", empty_pdf, "application/pdf")},
    )
    assert response.status_code == 400
    assert "文字" in response.json()["detail"]

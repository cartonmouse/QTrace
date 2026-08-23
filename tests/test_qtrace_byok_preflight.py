from scripts.qtrace_byok_preflight import inspect_byok


def _write_fixture(root):
    files = {
        "backend/main.py": '\n'.join(
            (
                '@app.post("/api/settings/test-llm")',
                "LLMConnectionRequest",
                ".probe()",
                '"ok": False',
            )
        ),
        "backend/models.py": "class LLMConnectionRequest\napi_base: str\napi_key: str",
        "backend/provider.py": '\n'.join(
            (
                "def probe(self)",
                '"max_tokens"',
                "max(1, min(int(max_tokens), 16))",
            )
        ),
        "backend/network_policy.py": '\n'.join(
            (
                "class APIBasePolicyError",
                "validate_api_base",
                "is_global",
            )
        ),
        "frontend/src/api/interview.ts": '\n'.join(
            (
                '`${API_BASE}/settings/test-llm`',
                'method: "POST"',
                "await readJson<AnyRecord>(res)",
            )
        ),
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def test_byok_preflight_accepts_probe_contract(tmp_path):
    _write_fixture(tmp_path)
    assert inspect_byok(tmp_path) == {
        "missing_files": [],
        "missing_markers": {},
        "forbidden_frontend_markers": [],
    }


def test_byok_preflight_rejects_placeholder_adapter(tmp_path):
    _write_fixture(tmp_path)
    adapter = tmp_path / "frontend/src/api/interview.ts"
    adapter.write_text(
        adapter.read_text(encoding="utf-8") + "\n当前 QTrace 尚未提供独立 LLM 连接测试接口",
        encoding="utf-8",
    )
    report = inspect_byok(tmp_path)
    assert report["forbidden_frontend_markers"]

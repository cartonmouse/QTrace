from pathlib import Path

from urllib.error import URLError

from scripts import local_runtime_smoke


class FakeResponse:
    def __init__(self, status: int = 200, body: bytes = b"ok"):
        self.status = status
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, limit: int):
        return self.body[:limit]


def _write_dist(root: Path, *, missing_asset: bool = False) -> None:
    dist = root / "frontend" / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text(
        '<link href="/assets/index.css"><script src="/assets/index.js"></script>',
        encoding="utf-8",
    )
    (assets / "index.css").write_text("body{}", encoding="utf-8")
    if not missing_asset:
        (assets / "index.js").write_text("console.log('qtrace');", encoding="utf-8")


def test_local_runtime_smoke_passes_without_printing_response_content(tmp_path, monkeypatch, capsys):
    _write_dist(tmp_path)
    seen_urls = []

    def fake_urlopen(request, timeout):
        seen_urls.append(request.full_url)
        return FakeResponse(body=b"synthetic response that must not be printed")

    monkeypatch.setattr(local_runtime_smoke, "urlopen", fake_urlopen)

    results = local_runtime_smoke.check_runtime(
        tmp_path,
        "http://127.0.0.1:8002/api/health",
        "http://127.0.0.1:5174/",
        0.1,
    )

    assert all(result.passed for result in results)
    assert seen_urls == ["http://127.0.0.1:8002/api/health", "http://127.0.0.1:5174/"]
    assert capsys.readouterr().out == ""


def test_local_runtime_smoke_reports_unreachable_local_services(tmp_path, monkeypatch):
    _write_dist(tmp_path)

    def fake_urlopen(request, timeout):
        raise URLError("synthetic local outage")

    monkeypatch.setattr(local_runtime_smoke, "urlopen", fake_urlopen)

    results = local_runtime_smoke.check_runtime(tmp_path, "http://backend", "http://frontend", 0.1)

    assert [result.status for result in results] == ["FAIL", "FAIL", "PASS"]
    assert results[0].detail == "unreachable or invalid response"


def test_local_runtime_smoke_reports_missing_bundled_asset(tmp_path, monkeypatch):
    _write_dist(tmp_path, missing_asset=True)
    monkeypatch.setattr(local_runtime_smoke, "urlopen", lambda request, timeout: FakeResponse())

    results = local_runtime_smoke.check_runtime(tmp_path, "http://backend", "http://frontend", 0.1)

    assert results[-1].status == "FAIL"
    assert results[-1].detail == "missing referenced assets=1"

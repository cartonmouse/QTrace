from scripts.qtrace_entry_preflight import inspect_entry


def _write_app(root, text):
    path = root / "frontend" / "src" / "App.tsx"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")


def test_qtrace_entry_preflight_accepts_direct_login_entry(tmp_path):
    _write_app(
        tmp_path,
        '''
function PublicHome() {
  return <Navigate to="/login" replace />;
}
function AuthPage() {
  return <Login />;
}
''',
    )

    assert inspect_entry(tmp_path) == {
        "missing_file": "",
        "missing_markers": [],
        "forbidden_markers": [],
    }


def test_qtrace_entry_preflight_reports_landing_as_active(tmp_path):
    _write_app(
        tmp_path,
        '''
import Landing from "./pages/Landing";
function PublicHome() {
  return <Landing />;
}
''',
    )

    report = inspect_entry(tmp_path)
    assert 'import Landing from "./pages/Landing";' in report["forbidden_markers"]
    assert "return <Landing />;" in report["forbidden_markers"]

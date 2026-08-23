from scripts.qtrace_profile_preflight import inspect_profile


def _write_fixture(root):
    page = root / "frontend/src/pages/Profile.jsx"
    style = root / "frontend/src/pages/qtrace-profile.css"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        '\n'.join(
            (
                'import "./qtrace-profile.css";',
                'className={cn(PAGE_CLASS, "qtrace-profile-page")}',
                "qtrace-profile-heading",
                "qtrace-profile-empty",
                "qtrace-profile-route-card",
                "qtrace-profile-stat-grid",
                "getProfile()",
                'navigate("/topic-drill")',
            )
        ),
        encoding="utf-8",
    )
    style.write_text(
        ".qtrace-profile-page .qtrace-profile-heading "
        ".qtrace-profile-surface .qtrace-profile-route-card "
        ".qtrace-profile-stat-grid\n"
        "@media (prefers-reduced-motion: reduce)",
        encoding="utf-8",
    )


def test_profile_has_qtrace_owned_landing_contract(tmp_path):
    _write_fixture(tmp_path)

    assert inspect_profile(tmp_path) == {
        "missing_files": [],
        "missing_page_markers": [],
        "missing_style_markers": [],
    }


def test_preflight_detects_removed_profile_surface(tmp_path):
    _write_fixture(tmp_path)
    (tmp_path / "frontend/src/pages/qtrace-profile.css").write_text(
        ".qtrace-profile-page", encoding="utf-8"
    )

    report = inspect_profile(tmp_path)

    assert ".qtrace-profile-route-card" in report["missing_style_markers"]

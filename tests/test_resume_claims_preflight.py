from scripts.resume_claims_preflight import (
    CLAIM_EVIDENCE,
    ENTRY_PATH,
    REQUIRED_SECTIONS,
    inspect_resume_entry,
)


def _write_complete_entry(root):
    entry = root / ENTRY_PATH
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("\n".join(REQUIRED_SECTIONS), encoding="utf-8")
    for paths in CLAIM_EVIDENCE.values():
        for relative in paths:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic evidence", encoding="utf-8")


def test_resume_claims_preflight_accepts_complete_synthetic_entry(tmp_path):
    _write_complete_entry(tmp_path)

    report = inspect_resume_entry(tmp_path)

    assert report == {
        "missing_file": "",
        "missing_sections": [],
        "missing_evidence": {},
    }


def test_resume_claims_preflight_reports_missing_section_and_evidence(tmp_path):
    entry = tmp_path / ENTRY_PATH
    entry.parent.mkdir(parents=True)
    entry.write_text(REQUIRED_SECTIONS[0], encoding="utf-8")

    report = inspect_resume_entry(tmp_path)

    assert REQUIRED_SECTIONS[1] in report["missing_sections"]
    assert "Agent工具链" in report["missing_evidence"]
    assert report["missing_evidence"]["Agent工具链"] == list(CLAIM_EVIDENCE["Agent工具链"])

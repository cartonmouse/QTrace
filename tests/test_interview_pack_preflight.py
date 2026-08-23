from scripts.interview_pack_preflight import REQUIRED_SECTIONS, inspect_interview_pack


def test_interview_pack_preflight_accepts_complete_synthetic_pack(tmp_path):
    path = tmp_path / "docs" / "STAGE55_INTERVIEW_DEFENSE_PACK.md"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(REQUIRED_SECTIONS), encoding="utf-8")

    report = inspect_interview_pack(tmp_path)

    assert report == {"missing_file": "", "missing_sections": []}


def test_interview_pack_preflight_reports_missing_pack_and_section(tmp_path):
    missing_file = inspect_interview_pack(tmp_path)
    assert missing_file["missing_file"] == "docs/STAGE55_INTERVIEW_DEFENSE_PACK.md"

    path = tmp_path / "docs" / "STAGE55_INTERVIEW_DEFENSE_PACK.md"
    path.parent.mkdir(parents=True)
    path.write_text(REQUIRED_SECTIONS[0], encoding="utf-8")

    report = inspect_interview_pack(tmp_path)

    assert REQUIRED_SECTIONS[1] in report["missing_sections"]

from scripts.synthetic_demo_smoke import run_demo


def test_synthetic_demo_rehearsal_covers_main_learning_loop(tmp_path):
    steps = run_demo(tmp_path / "synthetic-demo.sqlite3")

    names = [step.name for step in steps]
    assert names == [
        "register",
        "stub_provider",
        "resume_editor",
        "question_cards",
        "knowledge_graph",
        "agent_draft",
        "plan_confirm",
        "plan_complete",
    ]
    assert steps[-1].detail.startswith("status=completed")

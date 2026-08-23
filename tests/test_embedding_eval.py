from __future__ import annotations

from pathlib import Path

from scripts import embedding_eval


class _FakeProvider:
    mode = "synthetic-fake"
    dimension = 2

    _vectors = {
        "query-a": [1.0, 0.0],
        "query-b": [0.0, 1.0],
        "doc-a": [1.0, 0.0],
        "doc-b": [0.0, 1.0],
        "doc-distractor": [-1.0, 0.0],
    }

    def embed(self, text: str) -> list[float]:
        return self._vectors[text]


def test_evaluate_provider_calculates_recall_at_k_and_mrr():
    documents = (
        embedding_eval.SyntheticDocument("a", "doc-a"),
        embedding_eval.SyntheticDocument("b", "doc-b"),
        embedding_eval.SyntheticDocument("d", "doc-distractor"),
    )
    queries = (
        embedding_eval.SyntheticQuery("qa", "query-a", frozenset({"a"})),
        embedding_eval.SyntheticQuery("qb", "query-b", frozenset({"b"})),
    )

    result = embedding_eval.evaluate_provider(
        _FakeProvider(),
        documents=documents,
        queries=queries,
        top_k=1,
    )

    assert result.provider_mode == "synthetic-fake"
    assert result.dimension == 2
    assert result.recall_at_k == 1.0
    assert result.mrr == 1.0
    assert result.rankings == (("a", "b", "d"), ("b", "a", "d"))


def test_rank_documents_is_deterministic_for_equal_scores():
    documents = (
        embedding_eval.SyntheticDocument("b", "doc-b"),
        embedding_eval.SyntheticDocument("a", "doc-a"),
    )

    ranking = embedding_eval.rank_documents(_FakeProvider(), "query-a", documents)

    assert ranking == ("a", "b")


def test_cli_defaults_to_synthetic_deterministic_provider(capsys):
    result = embedding_eval.main([])

    assert result == 0
    output = capsys.readouterr().out
    assert "provider=local-deterministic" in output
    assert "recall@2=" in output
    assert "SKIP: 未提供本地模型目录" in output
    assert "network=disabled" in output


def test_cli_rejects_missing_model_directory_without_remote_request(tmp_path: Path, capsys):
    result = embedding_eval.main(["--model-path", str(tmp_path / "missing-model")])

    assert result == 1
    assert "FAIL: synthetic Embedding 检索评估失败" in capsys.readouterr().out

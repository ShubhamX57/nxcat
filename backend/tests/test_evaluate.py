import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from nxcat.ai import evaluate as ev
from nxcat.ai.filterspec import FilterSpec
from nxcat.ai.proposer import propose

QUESTIONS_PATH = Path(__file__).parent / "ai_eval" / "questions.json"
QUESTIONS: dict[str, Any] = json.loads(QUESTIONS_PATH.read_text())


def oracle(messages: list[dict[str, str]]) -> str:
    """A perfect model: answers every question exactly as the set expects."""
    item = next(q for q in QUESTIONS["questions"] if q["question"] == messages[1]["content"])
    expected = item["expected"]
    if "filter" in expected:
        return json.dumps({"filter": expected["filter"]})
    return json.dumps({expected["reject"]: "because"})


def test_question_set_has_the_planned_shape() -> None:
    categories = [q["category"] for q in QUESTIONS["questions"]]
    assert categories.count("normal") == 20
    assert categories.count("ambiguous") == 5
    assert categories.count("out_of_scope") == 5
    assert len({q["id"] for q in QUESTIONS["questions"]}) == 30


def test_every_expected_filter_is_itself_valid() -> None:
    for item in QUESTIONS["questions"]:
        if "filter" in item["expected"]:
            spec = FilterSpec.model_validate(item["expected"]["filter"])
            spec.check_instrument(set(QUESTIONS["instruments"]))


def test_a_perfect_model_scores_full_marks() -> None:
    summary = ev.summarise(ev.evaluate(QUESTIONS, oracle))
    assert (summary.exact, summary.normal) == (20, 20)
    assert (summary.rejected_out_of_scope, summary.out_of_scope) == (5, 5)
    assert (summary.clarified_ambiguous, summary.ambiguous) == (5, 5)
    assert summary.invalid_executed == 0
    assert summary.guardrail_caught == 0


def test_a_model_that_talks_instead_of_filtering_scores_zero_but_runs_nothing() -> None:
    summary = ev.summarise(ev.evaluate(QUESTIONS, lambda m: "Here are your results!"))
    assert summary.exact == 0
    assert summary.rejected_out_of_scope == 0
    assert summary.invalid_executed == 0
    assert summary.guardrail_caught == 30


def test_a_model_that_filters_everything_fails_the_rejection_questions() -> None:
    summary = ev.summarise(ev.evaluate(QUESTIONS, lambda m: '{"filter": {"q": "water"}}'))
    assert summary.rejected_out_of_scope == 0
    assert summary.clarified_ambiguous == 0
    assert summary.exact == 0


def test_free_text_case_does_not_matter_but_values_do() -> None:
    item = {
        "id": "x",
        "category": "normal",
        "question": "q",
        "expected": {"filter": {"q": "LiFePO4"}},
    }
    instruments: set[str] = set()
    assert ev.score_one(
        item,
        propose("q", lambda m: '{"filter": {"q": "lifepo4"}}', instruments, date(2026, 1, 1)),
    ).correct
    assert not ev.score_one(
        item,
        propose(
            "q",
            lambda m: '{"filter": {"q": "LiFePO4", "temp_min": 1}}',
            instruments,
            date(2026, 1, 1),
        ),
    ).correct


def test_cache_records_and_replays(tmp_path: Path) -> None:
    cache = tmp_path / "cache.json"
    first = ev.CachedModel("m", oracle, cache)
    ev.evaluate(QUESTIONS, first)
    first.save()
    assert first.calls == 30

    replay = ev.CachedModel("m", None, cache)  # no model at all
    summary = ev.summarise(ev.evaluate(QUESTIONS, replay))
    assert replay.calls == 0
    assert summary.exact == 20


def test_replay_without_cache_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(LookupError, match="not in cache"):
        ev.evaluate(QUESTIONS, ev.CachedModel("m", None, tmp_path / "none.json"))


def test_cache_is_per_model(tmp_path: Path) -> None:
    messages = [{"role": "user", "content": "hi"}]
    assert ev.CachedModel("a", None, tmp_path / "c").key(messages) != ev.CachedModel(
        "b", None, tmp_path / "c"
    ).key(messages)


def test_cli_writes_report_and_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(ev, "litellm_completer", lambda model, base, timeout: oracle)
    out = tmp_path / "report.md"
    cache = tmp_path / "cache.json"
    args = [
        "--model",
        "fake/model",
        "--questions",
        str(QUESTIONS_PATH),
        "--cache",
        str(cache),
        "--out",
        str(out),
    ]
    ev.main(args)
    printed = capsys.readouterr().out
    assert "exact 20/20" in printed
    assert "invalid executed 0" in printed
    text = out.read_text()
    assert "**20/20**" in text
    assert "| n01 | LET runs on benzene above 250 K from 2025 |" in text
    assert cache.exists()

    ev.main([*args, "--replay-only"])  # second run needs no model
    assert "model calls 0" in capsys.readouterr().out

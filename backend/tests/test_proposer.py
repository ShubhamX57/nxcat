import json
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from nxcat.ai.filterspec import FilterSpec, describe
from nxcat.ai.proposer import (
    MAX_QUESTION_LENGTH,
    RETRY_MESSAGE,
    Proposal,
    Rejection,
    build_messages,
    litellm_completer,
    parse_reply,
    propose,
)
from nxcat.api.schemas import SearchFilters
from nxcat.models.metadata import Technique

KNOWN = {"LET", "MARI", "LOKI"}
TODAY = date(2026, 10, 22)


def reply(obj: Any) -> str:
    return json.dumps(obj)


# --- valid proposals ---


def test_full_filter_is_converted_and_described() -> None:
    outcome = parse_reply(
        reply(
            {
                "filter": {
                    "instrument": "let",
                    "q": "benzene",
                    "temp_min": 250,
                    "start_after": "2025-01-01",
                    "start_before": "2026-01-01",
                }
            }
        ),
        KNOWN,
    )
    assert isinstance(outcome, Proposal)
    f = outcome.filters
    assert f.instrument == "LET"
    assert f.q == "benzene"
    assert f.temp_min == 250
    assert f.start_after == datetime(2025, 1, 1, tzinfo=UTC)
    assert f.start_before == datetime(2026, 1, 1, tzinfo=UTC)
    assert outcome.description == [
        "Instrument is LET",
        'Title, sample or instrument contains "benzene"',
        "Temperature at least 250 K",
        "Started on or after 2025-01-01",
        "Started before 2026-01-01",
    ]


@pytest.mark.parametrize(
    "text",
    [
        '```json\n{"filter": {"technique": "SANS"}}\n```',
        '```\n{"filter": {"technique": "SANS"}}\n```',
        '  {"filter": {"technique": "SANS"}}  ',
    ],
)
def test_code_fences_and_spaces_are_tolerated(text: str) -> None:
    outcome = parse_reply(text, KNOWN)
    assert isinstance(outcome, Proposal)
    assert outcome.filters.technique is Technique.SANS


# --- the model declines ---


def test_out_of_scope_keeps_the_models_reason() -> None:
    outcome = parse_reply(reply({"out_of_scope": "a science question"}), KNOWN)
    assert outcome == Rejection("out_of_scope", "a science question")


def test_unclear_without_a_reason_gets_a_default() -> None:
    outcome = parse_reply(reply({"unclear": ""}), KNOWN)
    assert outcome == Rejection("unclear", "Please make the question more specific.")


def test_long_reasons_are_cut() -> None:
    outcome = parse_reply(reply({"out_of_scope": "x" * 1000}), KNOWN)
    assert isinstance(outcome, Rejection)
    assert len(outcome.reason) == 300


# --- guardrails: anything wrong becomes an "invalid" rejection, never a search ---


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Sure! Here are the LET runs: run 1, run 2",  # model answered instead of filtering
        "not json at all {",
        "[]",
        reply(["filter"]),
        reply({}),
        reply({"filter": {"technique": "QENS"}, "out_of_scope": "both"}),  # two answers
        reply({"answer": "42"}),  # unknown key
        reply({"filter": "technique=QENS"}),  # not an object
        reply({"filter": {}}),  # empty filter
        reply({"filter": {"technique": "MAGIC"}}),  # unknown technique
        reply({"filter": {"instrument": "HAL9000"}}),  # instrument not in the catalogue
        reply({"filter": {"temp_min": -5}}),  # impossible value
        reply({"filter": {"temp_min": "warm"}}),  # wrong type
        reply({"filter": {"temp_min": 300, "temp_max": 10}}),  # reversed range
        reply({"filter": {"start_after": "2026-01-01", "start_before": "2025-01-01"}}),
        reply({"filter": {"start_after": "last tuesday"}}),  # not a date
        reply({"filter": {"technique": "QENS", "sql": "DROP TABLE dataset"}}),  # extra field
        reply({"filter": {"q": "x" * 201}}),  # too long
    ],
)
def test_bad_replies_are_rejected_as_invalid(text: str) -> None:
    assert parse_reply(text, KNOWN) == Rejection("invalid", RETRY_MESSAGE)


# --- prompt and propose() ---


def test_prompt_lists_instruments_techniques_and_today() -> None:
    system, user = build_messages("LET runs", {"MARI", "LET"}, TODAY)
    assert system["role"] == "system"
    assert "LET, MARI" in system["content"]
    assert "QENS" in system["content"]
    assert "Today is 2026-10-22" in system["content"]
    assert user == {"role": "user", "content": "LET runs"}  # question kept separate


def test_propose_calls_the_model_once_and_parses() -> None:
    calls: list[list[dict[str, str]]] = []

    def fake(messages: list[dict[str, str]]) -> str:
        calls.append(messages)
        return reply({"filter": {"instrument": "MARI"}})

    outcome = propose("  MARI runs  ", fake, {"MARI"}, TODAY)
    assert isinstance(outcome, Proposal)
    assert outcome.filters.instrument == "MARI"
    assert len(calls) == 1
    assert calls[0][1]["content"] == "MARI runs"


@pytest.mark.parametrize("question", ["", "   ", "x" * (MAX_QUESTION_LENGTH + 1)])
def test_empty_or_long_questions_never_reach_the_model(question: str) -> None:
    def must_not_be_called(messages: list[dict[str, str]]) -> str:
        raise AssertionError("model called")

    outcome = propose(question, must_not_be_called, KNOWN, TODAY)
    assert isinstance(outcome, Rejection)
    assert outcome.kind == "unclear"


def test_litellm_completer_sends_settings_and_returns_text(monkeypatch: pytest.MonkeyPatch) -> None:
    import litellm

    seen: dict[str, Any] = {}

    def fake_completion(**kwargs: Any) -> Any:
        seen.update(kwargs)
        message = SimpleNamespace(content='{"filter": {"technique": "INS"}}')
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(litellm, "completion", fake_completion)
    complete = litellm_completer("ollama/test", "http://model:11434", timeout=5)
    assert complete([{"role": "user", "content": "hi"}]) == '{"filter": {"technique": "INS"}}'
    assert seen["model"] == "ollama/test"
    assert seen["api_base"] == "http://model:11434"
    assert seen["temperature"] == 0
    assert seen["timeout"] == 5


def test_litellm_completer_handles_an_empty_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    import litellm

    def fake_completion(**kwargs: Any) -> Any:
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None))])

    monkeypatch.setattr(litellm, "completion", fake_completion)
    assert litellm_completer("m")([]) == ""


# --- FilterSpec and describe ---


def test_describe_covers_every_field() -> None:
    f = SearchFilters(technique=Technique.QENS, temp_max=20.5)
    assert describe(f) == ["Technique is QENS", "Temperature at most 20.5 K"]
    assert describe(SearchFilters(temp_min=200, temp_max=300)) == [
        "Temperature from 200 K to 300 K"
    ]


def test_filterspec_rejects_unknown_instrument_case_insensitively() -> None:
    spec = FilterSpec(instrument="let")
    spec.check_instrument({"LET"})
    with pytest.raises(ValueError, match="unknown instrument"):
        FilterSpec(instrument="ZEBRA").check_instrument({"LET"})

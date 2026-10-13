"""Evaluate plain-English search on the fixed question set (plan section 8).

Reports the plan's three numbers:
  1. exact matches on the 20 normal questions;
  2. out-of-scope questions correctly rejected (of 5);
  3. invalid filters executed, which must be 0.
It also reports how the 5 ambiguous questions were handled and how often the
guardrails caught a bad model reply.

Every model reply is cached (keyed by model and exact prompt), so a run can be
repeated, checked or re-scored without calling the model again.

    uv run nxcat-eval --model ollama/qwen2.5:7b-instruct --api-base http://localhost:11434
"""

import argparse
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from nxcat.ai.filterspec import FilterSpec
from nxcat.ai.proposer import (
    Complete,
    Proposal,
    Rejection,
    build_messages,
    litellm_completer,
    propose,
)
from nxcat.api.schemas import SearchFilters

DEFAULT_QUESTIONS = Path("tests/ai_eval/questions.json")
DEFAULT_CACHE = Path("tests/ai_eval/cache.json")
DEFAULT_REPORT = Path("../docs/ai-evaluation.md")


@dataclass(frozen=True)
class Result:
    id: str
    category: str
    question: str
    expected: str
    got: str
    correct: bool
    guardrail_caught: bool  # the model's reply was rejected as invalid
    executed_invalid: bool  # a proposal that would not pass the search API's validation


@dataclass(frozen=True)
class Summary:
    exact: int
    normal: int
    rejected_out_of_scope: int
    out_of_scope: int
    clarified_ambiguous: int
    ambiguous: int
    invalid_executed: int
    guardrail_caught: int
    total: int


def _show(filters: SearchFilters) -> str:
    return json.dumps(filters.model_dump(mode="json", exclude_none=True), sort_keys=True)


def _same(a: SearchFilters, b: SearchFilters) -> bool:
    """Exact match, except that free text is compared without regard to case."""
    da, db = a.model_dump(), b.model_dump()
    da["q"] = (da["q"] or "").casefold() or None
    db["q"] = (db["q"] or "").casefold() or None
    return da == db


def score_one(item: dict[str, Any], outcome: Proposal | Rejection) -> Result:
    expected = item["expected"]
    if "filter" in expected:
        want = FilterSpec.model_validate(expected["filter"]).to_search_filters()
        expected_text = _show(want)
        correct = isinstance(outcome, Proposal) and _same(outcome.filters, want)
    else:
        expected_text = f"reject ({expected['reject']})"
        correct = isinstance(outcome, Rejection) and outcome.kind == expected["reject"]

    executed_invalid = False
    if isinstance(outcome, Proposal):
        got = _show(outcome.filters)
        # The guarantee being measured: whatever is proposed must pass the same
        # validation as a normal search request before it could ever run.
        try:
            SearchFilters.model_validate(outcome.filters.model_dump())
        except ValidationError:
            executed_invalid = True
    else:
        got = f"reject ({outcome.kind})"

    return Result(
        id=item["id"],
        category=item["category"],
        question=item["question"],
        expected=expected_text,
        got=got,
        correct=correct,
        guardrail_caught=isinstance(outcome, Rejection) and outcome.kind == "invalid",
        executed_invalid=executed_invalid,
    )


def summarise(results: Sequence[Result]) -> Summary:
    def count(category: str, *, correct: bool | None = None) -> int:
        return sum(
            1
            for r in results
            if r.category == category and (correct is None or r.correct == correct)
        )

    return Summary(
        exact=count("normal", correct=True),
        normal=count("normal"),
        rejected_out_of_scope=count("out_of_scope", correct=True),
        out_of_scope=count("out_of_scope"),
        clarified_ambiguous=count("ambiguous", correct=True),
        ambiguous=count("ambiguous"),
        invalid_executed=sum(r.executed_invalid for r in results),
        guardrail_caught=sum(r.guardrail_caught for r in results),
        total=len(results),
    )


class CachedModel:
    """Wraps a model so each exact prompt is sent at most once and replies are kept."""

    def __init__(self, model: str, complete: Complete | None, cache_path: Path) -> None:
        self.model = model
        self.complete = complete
        self.path = cache_path
        self.entries: dict[str, str] = (
            json.loads(cache_path.read_text()) if cache_path.exists() else {}
        )
        self.calls = 0

    def key(self, messages: list[dict[str, str]]) -> str:
        raw = json.dumps({"model": self.model, "messages": messages}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def __call__(self, messages: list[dict[str, str]]) -> str:
        key = self.key(messages)
        if key not in self.entries:
            if self.complete is None:
                raise LookupError("reply not in cache and --replay-only was given")
            self.entries[key] = self.complete(messages)
            self.calls += 1
        return self.entries[key]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.entries, indent=1, sort_keys=True) + "\n")


def evaluate(questions: dict[str, Any], complete: Complete) -> list[Result]:
    today = date.fromisoformat(questions["today"])
    instruments = set(questions["instruments"])
    return [
        score_one(item, propose(item["question"], complete, instruments, today))
        for item in questions["questions"]
    ]


def report(summary: Summary, results: Sequence[Result], model: str) -> str:
    when = datetime.now(UTC).strftime("%Y-%m-%d")
    s = summary
    rows = "\n".join(
        f"| {r.id} | {r.question} | `{r.expected}` | `{r.got}` | {'✓' if r.correct else '✗'} |"
        for r in results
    )
    return f"""# Plain-English search: evaluation

Model: `{model}` · Date: {when} · Questions: {summary.total} \
(`backend/tests/ai_eval/questions.json`)

| Measure | Result |
|---|---|
| Normal questions: filter exactly as expected | **{summary.exact}/{summary.normal}** |
| Out-of-scope questions correctly rejected | **{s.rejected_out_of_scope}/{s.out_of_scope}** |
| Invalid filters executed | **{summary.invalid_executed}** |
| Ambiguous questions where the model asked to clarify | {s.clarified_ambiguous}/{s.ambiguous} |
| Model replies stopped by the guardrails (invalid) | {summary.guardrail_caught} |

Notes:
- "Exact" means every field equal; free text is compared without regard to case.
- The ask endpoint never runs a search, so a wrong proposal can only be shown to the
  user, who must confirm it. "Invalid filters executed" checks that every proposal
  would pass the search API's own validation.
- Replies are cached in `backend/tests/ai_eval/cache.json`, so this run can be repeated
  with `uv run nxcat-eval --model {model} --replay-only`.

## Every question

| ID | Question | Expected | Got | |
|---|---|---|---|---|
{rows}
"""


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluate plain-English search.")
    parser.add_argument(
        "--model", required=True, help='LiteLLM model, e.g. "ollama/qwen2.5:7b-instruct"'
    )
    parser.add_argument("--api-base", help="model server address, e.g. http://localhost:11434")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--replay-only", action="store_true", help="use cached replies only")
    args = parser.parse_args(argv)

    live = None if args.replay_only else litellm_completer(args.model, args.api_base, timeout=120)
    model = CachedModel(args.model, live, args.cache)
    try:
        results = evaluate(json.loads(args.questions.read_text()), model)
    finally:
        model.save()  # keep whatever was answered, even if a later call fails
    summary = summarise(results)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report(summary, results, args.model))
    print(
        f"exact {summary.exact}/{summary.normal} · "
        f"out of scope rejected {summary.rejected_out_of_scope}/{summary.out_of_scope} · "
        f"invalid executed {summary.invalid_executed} · "
        f"ambiguous clarified {summary.clarified_ambiguous}/{summary.ambiguous} · "
        f"model calls {model.calls} · report: {args.out}"
    )


__all__ = ["CachedModel", "build_messages", "evaluate", "main", "report", "summarise"]

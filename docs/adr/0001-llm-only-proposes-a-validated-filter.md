# 1. The language model only proposes a validated filter

Status: accepted · Date: 2026-10-13

## Context

nxcat lets scientists ask for datasets in plain English. Language models can be wrong
with confidence, and in a scientific catalogue a confident wrong answer (a missing run,
an invented result) is worse than no answer. User input also reaches the model, so a
question could try to make it do something else ("prompt injection").

## Decision

The model has one job: turn a question into a **search filter**, or say it cannot.

1. Its reply must be exactly one JSON object: a filter, `out_of_scope`, or `unclear`.
   Anything else is rejected.
2. A filter must pass `FilterSpec` (pydantic: known fields only, correct types, possible
   values, a known instrument) and then the search API's own `SearchFilters` validation.
3. `POST /api/v1/search/ask` returns the *proposal* only. It never runs a search and
   never returns datasets.
4. nxcat's own code, not the model, writes the plain-words description, so what the user
   reads is exactly what will run.
5. The search runs only when the user presses **Run**, through the normal search endpoint.
6. The model sits behind LiteLLM, so it can be a local model (Ollama) or a hosted one.

## Consequences

- A wrong proposal can at worst be shown to the user, who can see it is wrong.
- Prompt injection can at worst produce a valid-but-unwanted filter, never an action.
- Questions the filter fields cannot express (e.g. "datasets with good statistics")
  are rejected, even when a human would understand them.
- The quality is measured, not assumed: 30 fixed questions, with the real numbers in
  the README (`backend/tests/ai_eval/`).

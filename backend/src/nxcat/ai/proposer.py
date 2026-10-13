"""Turn a plain-English question into a *proposed* filter, or a reasoned rejection.

The flow is: build a prompt -> ask the model -> parse its reply strictly -> validate.
Nothing here touches the database or runs a search. The model is reached through
LiteLLM, so it can be swapped (a local Ollama model, a hosted one) by configuration.
"""

import json
import re
from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from pydantic import ValidationError

from nxcat.ai.filterspec import FilterSpec, describe
from nxcat.api.schemas import SearchFilters
from nxcat.models.metadata import Technique

MAX_QUESTION_LENGTH = 300

# A function that sends chat messages to a model and returns its text reply.
Complete = Callable[[list[dict[str, str]]], str]


@dataclass(frozen=True)
class Proposal:
    filters: SearchFilters
    description: list[str]


RejectionKind = Literal["out_of_scope", "unclear", "invalid"]


@dataclass(frozen=True)
class Rejection:
    kind: RejectionKind
    reason: str


Outcome = Proposal | Rejection

RETRY_MESSAGE = "I could not turn that into a valid search. Please rephrase it."

SYSTEM_PROMPT = """\
You turn a scientist's question into a search filter for nxcat, a catalogue of \
neutron scattering datasets. You never answer the question yourself and never \
invent data. Reply with ONE JSON object and nothing else, in one of three forms:

1. {{"filter": {{...}}}} when the question is a search for datasets.
2. {{"out_of_scope": "<short reason>"}} when it is not a search for datasets \
(a science question, a request to change or delete data, anything else).
3. {{"unclear": "<what to clarify>"}} when it is a search but too vague to turn \
into exact values (for example "cold", "recent", "big", or a name that matches \
several samples).

Filter fields (all optional, but at least one is required):
- "q": text to find in the title or sample name, e.g. a sample such as "benzene".
  Do not put instrument or technique names in "q".
- "instrument": one of {instruments}.
- "technique": one of {techniques}.
- "temp_min", "temp_max": sample temperature in kelvin (numbers). Convert Celsius \
to kelvin by adding 273.15.
- "start_after": first day to include, "YYYY-MM-DD".
- "start_before": first day to EXCLUDE, "YYYY-MM-DD". "In 2025" means \
start_after 2025-01-01 and start_before 2026-01-01.

Use only these fields. Only set a field the question asks for. Today is {today}.

Examples:
Q: LET runs on benzene above 250 K from 2025
A: {{"filter": {{"instrument": "LET", "q": "benzene", "temp_min": 250, \
"start_after": "2025-01-01", "start_before": "2026-01-01"}}}}
Q: SANS measurements below 20 K
A: {{"filter": {{"technique": "SANS", "temp_max": 20}}}}
Q: What is the boiling point of water?
A: {{"out_of_scope": "this is a science question, not a search for datasets"}}
Q: show me the hot runs
A: {{"unclear": "which temperature counts as hot, in kelvin?"}}
"""


def build_messages(
    question: str, instruments: Collection[str], today: date
) -> list[dict[str, str]]:
    system = SYSTEM_PROMPT.format(
        instruments=", ".join(sorted(instruments)) or "(none yet)",
        techniques=", ".join(t.value for t in Technique),
        today=today.isoformat(),
    )
    # The question goes in its own message and is never mixed into the instructions.
    return [{"role": "system", "content": system}, {"role": "user", "content": question}]


def parse_reply(reply: str, instruments: set[str]) -> Outcome:
    """Strictly interpret the model's reply. Anything unexpected becomes a rejection."""
    data = _json_object(reply)
    if data is None or len(data) != 1:
        return Rejection("invalid", RETRY_MESSAGE)

    ((key, value),) = data.items()
    if key == "out_of_scope":
        return Rejection("out_of_scope", _reason(value, "That is not a search for datasets."))
    if key == "unclear":
        return Rejection("unclear", _reason(value, "Please make the question more specific."))
    if key != "filter" or not isinstance(value, dict):
        return Rejection("invalid", RETRY_MESSAGE)

    try:
        spec = FilterSpec.model_validate(value)
        spec.check_instrument(instruments)
        filters = spec.to_search_filters()
    except (ValidationError, ValueError):
        return Rejection("invalid", RETRY_MESSAGE)
    return Proposal(filters=filters, description=describe(filters))


def _reason(value: object, default: str) -> str:
    """The model's short explanation, or a default. Never longer than 300 characters."""
    text = value.strip() if isinstance(value, str) else ""
    return (text or default)[:300]


def _json_object(reply: str) -> dict[str, Any] | None:
    """The JSON object in the reply, tolerating ```json fences around it."""
    text = reply.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def propose(question: str, complete: Complete, instruments: set[str], today: date) -> Outcome:
    """Ask the model for a filter. Errors talking to the model propagate to the caller."""
    question = question.strip()
    if not question:
        return Rejection("unclear", "Please type a question.")
    if len(question) > MAX_QUESTION_LENGTH:
        return Rejection(
            "unclear", f"Please keep the question under {MAX_QUESTION_LENGTH} characters."
        )
    reply = complete(build_messages(question, instruments, today))
    return parse_reply(reply, {name.upper() for name in instruments})


def litellm_completer(model: str, api_base: str | None = None, timeout: float = 30.0) -> Complete:
    """A `Complete` function backed by LiteLLM (imported lazily: it is slow to import)."""

    def complete(messages: list[dict[str, str]]) -> str:
        import litellm

        response = litellm.completion(
            model=model,
            messages=messages,
            api_base=api_base,
            temperature=0,  # the same question should give the same filter
            max_tokens=300,
            timeout=timeout,
        )
        content = response.choices[0].message.content
        return content if isinstance(content, str) else ""

    return complete

"""What the language model is allowed to propose, and how it is checked.

The model never answers questions about the data and never runs a search. It may
only return one of three JSON shapes:

    {"filter": {...FilterSpec fields...}}
    {"out_of_scope": "why this is not a search"}
    {"unclear": "what the user should clarify"}

Anything else, or a filter that fails validation, is rejected. A valid FilterSpec is
converted to the API's own `SearchFilters`, so the plain-English search can never
ask for anything the normal search endpoint would not accept.
"""

from datetime import UTC, date, datetime, time
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from nxcat.api.schemas import SearchFilters
from nxcat.models.metadata import Technique


class FilterSpec(BaseModel):
    """The filter fields a model may propose. Dates are whole days (UTC)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    q: str | None = Field(default=None, min_length=1, max_length=200)
    instrument: str | None = Field(default=None, min_length=1, max_length=64)
    technique: Technique | None = None
    temp_min: float | None = Field(default=None, ge=0)
    temp_max: float | None = Field(default=None, ge=0)
    start_after: date | None = None  # on or after this day
    start_before: date | None = None  # before this day (exclusive)

    @model_validator(mode="after")
    def _not_empty(self) -> Self:
        if all(value is None for value in self.model_dump().values()):
            raise ValueError("the filter is empty")
        return self

    def check_instrument(self, known: set[str]) -> None:
        """Reject instruments that are not in the catalogue (a likely hallucination)."""
        if self.instrument is not None and self.instrument.upper() not in known:
            raise ValueError(f"unknown instrument {self.instrument!r}")

    def to_search_filters(self) -> SearchFilters:
        """Convert to the search API's filters; raises ValidationError if impossible."""

        def midnight(day: date | None) -> datetime | None:
            return None if day is None else datetime.combine(day, time(0, 0), tzinfo=UTC)

        return SearchFilters(
            q=self.q,
            instrument=self.instrument.upper() if self.instrument else None,
            technique=self.technique,
            temp_min=self.temp_min,
            temp_max=self.temp_max,
            start_after=midnight(self.start_after),
            start_before=midnight(self.start_before),
        )


def describe(filters: SearchFilters) -> list[str]:
    """The filter in plain words, written by our code (not by the model), so the
    description shown to the user always matches the search that will run."""
    parts: list[str] = []
    if filters.instrument:
        parts.append(f"Instrument is {filters.instrument}")
    if filters.technique:
        parts.append(f"Technique is {filters.technique.value}")
    if filters.q:
        parts.append(f'Title, sample or instrument contains "{filters.q}"')
    if filters.temp_min is not None and filters.temp_max is not None:
        parts.append(f"Temperature from {filters.temp_min:g} K to {filters.temp_max:g} K")
    elif filters.temp_min is not None:
        parts.append(f"Temperature at least {filters.temp_min:g} K")
    elif filters.temp_max is not None:
        parts.append(f"Temperature at most {filters.temp_max:g} K")
    if filters.start_after is not None:
        parts.append(f"Started on or after {filters.start_after.date().isoformat()}")
    if filters.start_before is not None:
        parts.append(f"Started before {filters.start_before.date().isoformat()}")
    return parts


__all__ = ["FilterSpec", "ValidationError", "describe"]

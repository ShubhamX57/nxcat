"""Turn validated `SearchFilters` into SQL conditions."""

from sqlalchemy import ColumnElement, func

from nxcat.api.schemas import SearchFilters
from nxcat.models.tables import Dataset


def conditions(filters: SearchFilters) -> list[ColumnElement[bool]]:
    """One SQL condition per filter that is set. All values are bound parameters."""
    where: list[ColumnElement[bool]] = []
    if filters.q is not None:
        # websearch_to_tsquery accepts anything a person types (quotes, "or", -word)
        # without raising a syntax error.
        where.append(
            Dataset.search_vector.op("@@")(func.websearch_to_tsquery("english", filters.q))
        )
    if filters.instrument is not None:
        where.append(Dataset.instrument == filters.instrument.strip().upper())
    if filters.technique is not None:
        where.append(Dataset.technique == filters.technique.value)
    if filters.temp_min is not None:
        where.append(Dataset.sample_temperature_k >= filters.temp_min)
    if filters.temp_max is not None:
        where.append(Dataset.sample_temperature_k <= filters.temp_max)
    if filters.start_after is not None:
        where.append(Dataset.start_time >= filters.start_after)
    if filters.start_before is not None:
        where.append(Dataset.start_time < filters.start_before)
    return where

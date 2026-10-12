"""Shapes of API requests and responses."""

from datetime import datetime
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from nxcat.models.metadata import Technique


class SearchFilters(BaseModel):
    """Every filter the search endpoint accepts.

    This is also the shape the plain-English search will be allowed to propose
    later, so the language model can never ask for anything the API can't check.
    """

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(default=None, min_length=1, max_length=200, description="free text")
    instrument: str | None = Field(default=None, min_length=1, max_length=64)
    technique: Technique | None = None
    temp_min: float | None = Field(default=None, ge=0, description="kelvin")
    temp_max: float | None = Field(default=None, ge=0, description="kelvin")
    start_after: AwareDatetime | None = None
    start_before: AwareDatetime | None = None

    @model_validator(mode="after")
    def _ranges_are_ordered(self) -> Self:
        if (
            self.temp_min is not None
            and self.temp_max is not None
            and self.temp_min > self.temp_max
        ):
            raise ValueError("temp_min must not be greater than temp_max")
        if (
            self.start_after is not None
            and self.start_before is not None
            and self.start_after > self.start_before
        ):
            raise ValueError("start_after must not be later than start_before")
        return self


class SearchQuery(SearchFilters):
    """Filters plus paging, as sent in the query string."""

    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    instrument: str
    technique: Technique
    run_number: int
    sample_name: str
    sample_temperature_k: float | None
    start_time: datetime
    end_time: datetime | None
    facility: str | None
    proposal_id: str | None
    file_path: str
    file_size_bytes: int
    checksum: str
    schema_version: str
    ingested_at: datetime


class DatasetPage(BaseModel):
    items: list[DatasetOut]
    total: int
    page: int
    size: int


class FacetCount(BaseModel):
    value: str
    count: int


class Facets(BaseModel):
    instrument: list[FacetCount]
    technique: list[FacetCount]


class Health(BaseModel):
    status: str
    database: str

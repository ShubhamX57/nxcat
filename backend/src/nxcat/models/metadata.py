"""Metadata schema: the contract every dataset must meet before it is stored.

`DatasetMetadata` holds only the fields read from a NeXus file. Fields that
nxcat creates itself (id, checksum, ingested_at, ...) belong to the database
record, which is defined separately.
"""

from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1"


class Technique(StrEnum):
    """Neutron techniques that nxcat knows about."""

    QENS = "QENS"
    INS = "INS"
    SANS = "SANS"
    DIFFRACTION = "DIFFRACTION"
    REFLECTOMETRY = "REFLECTOMETRY"
    IMAGING = "IMAGING"


class DatasetMetadata(BaseModel):
    """Metadata extracted from one NeXus/HDF5 file."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    title: str = Field(min_length=1)
    instrument: str = Field(min_length=1)
    technique: Technique
    run_number: int = Field(ge=0)
    sample_name: str = Field(min_length=1)
    start_time: AwareDatetime
    end_time: AwareDatetime | None = None
    sample_temperature_k: float | None = Field(default=None, gt=0)
    facility: str | None = None
    proposal_id: str | None = None

    @field_validator("instrument")
    @classmethod
    def _instrument_upper_case(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def _end_not_before_start(self) -> Self:
        if self.end_time is not None and self.end_time < self.start_time:
            raise ValueError("end_time must not be before start_time")
        return self

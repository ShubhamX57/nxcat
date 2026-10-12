"""Database tables (SQLAlchemy 2.0).

`dataset` holds one row per catalogued file. `ingest_error` keeps a record of
every file that could not be ingested, and why.
"""

from datetime import datetime

from sqlalchemy import BigInteger, Computed, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Full-text search over the fields a person is most likely to type.
SEARCH_EXPRESSION = (
    "to_tsvector('english', coalesce(title, '') || ' ' || "
    "coalesce(sample_name, '') || ' ' || coalesce(instrument, ''))"
)


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "dataset"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_path: Mapped[str] = mapped_column(Text, unique=True)
    checksum: Mapped[str] = mapped_column(String(64))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    schema_version: Mapped[str] = mapped_column(String(16))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Fields from DatasetMetadata
    title: Mapped[str] = mapped_column(Text)
    instrument: Mapped[str] = mapped_column(String(64), index=True)
    technique: Mapped[str] = mapped_column(String(32), index=True)
    run_number: Mapped[int]
    sample_name: Mapped[str] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sample_temperature_k: Mapped[float | None]
    facility: Mapped[str | None] = mapped_column(String(64))
    proposal_id: Mapped[str | None] = mapped_column(String(64))

    search_vector: Mapped[str] = mapped_column(
        TSVECTOR, Computed(SEARCH_EXPRESSION, persisted=True), deferred=True
    )

    __table_args__ = (Index("ix_dataset_search_vector", "search_vector", postgresql_using="gin"),)


class IngestError(Base):
    __tablename__ = "ingest_error"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_path: Mapped[str] = mapped_column(Text, index=True)
    reason: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

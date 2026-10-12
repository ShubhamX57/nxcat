from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from nxcat.models.metadata import DatasetMetadata, Technique


def valid_data() -> dict[str, Any]:
    """One valid example. Each test changes one thing."""
    return {
        "title": "Benzene QENS 260 K",
        "instrument": "LET",
        "technique": "QENS",
        "run_number": 12345,
        "sample_name": "benzene",
        "sample_temperature_k": 260.0,
        "start_time": datetime(2025, 3, 1, 10, 0, tzinfo=UTC),
        "end_time": datetime(2025, 3, 1, 12, 0, tzinfo=UTC),
    }


def test_valid_metadata_is_accepted() -> None:
    meta = DatasetMetadata.model_validate(valid_data())
    assert meta.instrument == "LET"
    assert meta.technique is Technique.QENS


def test_optional_fields_can_be_missing() -> None:
    data = valid_data()
    for field in ("end_time", "sample_temperature_k"):
        del data[field]
    meta = DatasetMetadata.model_validate(data)
    assert meta.end_time is None
    assert meta.sample_temperature_k is None


def test_instrument_is_stored_upper_case() -> None:
    data = valid_data() | {"instrument": "  let "}
    assert DatasetMetadata.model_validate(data).instrument == "LET"


def test_iso_strings_are_parsed() -> None:
    data = valid_data() | {"start_time": "2025-03-01T10:00:00Z", "end_time": None}
    assert DatasetMetadata.model_validate(data).start_time == datetime(2025, 3, 1, 10, tzinfo=UTC)


@pytest.mark.parametrize("temperature", [0.0, -5.0])
def test_non_positive_temperature_is_rejected(temperature: float) -> None:
    data = valid_data() | {"sample_temperature_k": temperature}
    with pytest.raises(ValidationError):
        DatasetMetadata.model_validate(data)


def test_end_before_start_is_rejected() -> None:
    data = valid_data() | {"end_time": datetime(2025, 3, 1, 9, 0, tzinfo=UTC)}
    with pytest.raises(ValidationError, match="end_time must not be before start_time"):
        DatasetMetadata.model_validate(data)


@pytest.mark.parametrize(
    "field", ["title", "instrument", "technique", "run_number", "sample_name", "start_time"]
)
def test_missing_required_field_is_rejected(field: str) -> None:
    data = valid_data()
    del data[field]
    with pytest.raises(ValidationError):
        DatasetMetadata.model_validate(data)


def test_empty_title_is_rejected() -> None:
    data = valid_data() | {"title": "   "}
    with pytest.raises(ValidationError):
        DatasetMetadata.model_validate(data)


def test_unknown_technique_is_rejected() -> None:
    data = valid_data() | {"technique": "MAGIC"}
    with pytest.raises(ValidationError):
        DatasetMetadata.model_validate(data)


def test_negative_run_number_is_rejected() -> None:
    data = valid_data() | {"run_number": -1}
    with pytest.raises(ValidationError):
        DatasetMetadata.model_validate(data)


def test_unknown_field_is_rejected() -> None:
    data = valid_data() | {"colour": "blue"}
    with pytest.raises(ValidationError):
        DatasetMetadata.model_validate(data)


def test_time_without_timezone_is_rejected() -> None:
    data = valid_data() | {"start_time": datetime(2025, 3, 1, 10, 0), "end_time": None}
    with pytest.raises(ValidationError):
        DatasetMetadata.model_validate(data)


def test_metadata_cannot_be_changed_after_validation() -> None:
    meta = DatasetMetadata.model_validate(valid_data())
    with pytest.raises(ValidationError):
        meta.title = "changed"  # type: ignore[misc]

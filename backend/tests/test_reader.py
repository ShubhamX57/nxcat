import hashlib
import random
from pathlib import Path

import h5py
import pytest

from nxcat.ingest.reader import ReadError, read_metadata, sha256_of
from nxcat.models.metadata import DatasetMetadata, Technique
from nxcat.synthetic import Broken, random_metadata, write_nexus


def broken_file(tmp_path: Path, kind: Broken) -> Path:
    rng = random.Random(5)
    return write_nexus(tmp_path / f"{kind.value}.nxs", random_metadata(rng, 1), rng, broken=kind)


def set_temperature(path: Path, value: object, units: str | None) -> None:
    with h5py.File(path, "a") as f:
        sample = f["entry/sample"]
        if "temperature" in sample:
            del sample["temperature"]
        sample["temperature"] = value
        if units is not None:
            sample["temperature"].attrs["units"] = units


def test_valid_file_round_trips(nexus_file: tuple[Path, DatasetMetadata]) -> None:
    path, meta = nexus_file
    assert read_metadata(path) == meta


@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        (Broken.MISSING_FIELD, "missing field /entry/title"),
        (Broken.WRONG_TYPE, "temperature must be a number"),
        (Broken.BAD_VALUE, "end_time must not be before start_time"),
        (Broken.TRUNCATED, "not a readable HDF5 file"),
        (Broken.NOT_HDF5, "not a readable HDF5 file"),
    ],
)
def test_broken_files_give_a_clear_reason(tmp_path: Path, kind: Broken, reason: str) -> None:
    with pytest.raises(ReadError, match=reason):
        read_metadata(broken_file(tmp_path, kind))


@pytest.mark.parametrize(
    ("value", "units", "kelvin"),
    [
        (300.0, "K", 300.0),
        (300.0, "kelvin", 300.0),
        (300.0, None, 300.0),  # no units attribute: NeXus default is kelvin
        (26.85, "degC", 300.0),
        (26.85, "celsius", 300.0),
        (1500.0, "mK", 1.5),
        (300, "K", 300.0),  # integers are fine
    ],
)
def test_temperature_is_converted_to_kelvin(
    nexus_file: tuple[Path, DatasetMetadata], value: float, units: str | None, kelvin: float
) -> None:
    path, _ = nexus_file
    set_temperature(path, value, units)
    assert read_metadata(path).sample_temperature_k == pytest.approx(kelvin)


def test_unknown_temperature_unit_is_rejected(nexus_file: tuple[Path, DatasetMetadata]) -> None:
    path, _ = nexus_file
    set_temperature(path, 80.0, "degF")
    with pytest.raises(ReadError, match="unknown temperature unit 'degF'"):
        read_metadata(path)


def test_temperature_below_absolute_zero_is_rejected(
    nexus_file: tuple[Path, DatasetMetadata],
) -> None:
    path, _ = nexus_file
    set_temperature(path, -300.0, "degC")
    with pytest.raises(ReadError, match="sample_temperature_k"):
        read_metadata(path)


def test_unknown_instrument_uses_definition(nexus_file: tuple[Path, DatasetMetadata]) -> None:
    path, _ = nexus_file
    with h5py.File(path, "a") as f:
        del f["entry/instrument/name"], f["entry/definition"]
        f["entry/instrument/name"] = "D22"
        f["entry/definition"] = "NXcanSAS"
    meta = read_metadata(path)
    assert meta.instrument == "D22"
    assert meta.technique is Technique.SANS


def test_unknown_instrument_and_definition_is_rejected(
    nexus_file: tuple[Path, DatasetMetadata],
) -> None:
    path, _ = nexus_file
    with h5py.File(path, "a") as f:
        del f["entry/instrument/name"], f["entry/definition"]
        f["entry/instrument/name"] = "D22"
        f["entry/definition"] = "NXspe"  # QENS or INS: can't decide
    with pytest.raises(ReadError, match="cannot work out the technique"):
        read_metadata(path)


def test_isis_raw_data_entry_name_is_supported(
    nexus_file: tuple[Path, DatasetMetadata],
) -> None:
    path, meta = nexus_file
    with h5py.File(path, "a") as f:
        f.move("entry", "raw_data_1")
    assert read_metadata(path) == meta


def test_entry_found_by_nx_class(nexus_file: tuple[Path, DatasetMetadata]) -> None:
    path, meta = nexus_file
    with h5py.File(path, "a") as f:
        f.move("entry", "scan_7")
    assert read_metadata(path) == meta


def test_file_without_entry_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "empty.nxs"
    with h5py.File(path, "w") as f:
        f.create_group("not_an_entry")
    with pytest.raises(ReadError, match="no NXentry group"):
        read_metadata(path)


def test_group_where_value_expected_is_rejected(
    nexus_file: tuple[Path, DatasetMetadata],
) -> None:
    path, _ = nexus_file
    with h5py.File(path, "a") as f:
        del f["entry/title"]
        f.create_group("entry/title")
    with pytest.raises(ReadError, match="is a group, not a value"):
        read_metadata(path)


def test_array_where_value_expected_is_rejected(
    nexus_file: tuple[Path, DatasetMetadata],
) -> None:
    path, _ = nexus_file
    with h5py.File(path, "a") as f:
        del f["entry/entry_identifier"]
        f["entry/entry_identifier"] = [1, 2, 3]
    with pytest.raises(ReadError, match="must be a single value"):
        read_metadata(path)


def test_one_element_array_and_bytes_are_accepted(
    nexus_file: tuple[Path, DatasetMetadata],
) -> None:
    path, meta = nexus_file
    with h5py.File(path, "a") as f:
        del f["entry/entry_identifier"], f["entry/title"]
        f["entry/entry_identifier"] = [meta.run_number]
        f["entry/title"] = meta.title.encode()  # fixed-length bytes, as older files store it
    assert read_metadata(path) == meta


def test_checksum_matches_hashlib(tmp_path: Path) -> None:
    path = tmp_path / "data.bin"
    content = b"neutrons" * 100_000
    path.write_bytes(content)
    assert sha256_of(path, chunk_size=4096) == hashlib.sha256(content).hexdigest()

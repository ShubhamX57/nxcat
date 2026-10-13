"""Read one NeXus/HDF5 file into validated `DatasetMetadata`.

Every problem with a file becomes a `ReadError` with a short, readable reason.
The ingest pipeline catches `ReadError`, records it and moves on to the next file.
"""

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import h5py
import numpy as np
from pydantic import ValidationError

from nxcat.instruments import DEFINITION_TECHNIQUE, INSTRUMENTS
from nxcat.models.metadata import DatasetMetadata, Technique

ENTRY_NAMES = ("entry", "raw_data_1")  # standard NeXus, and ISIS raw files

# Temperature unit (lower case) -> function that converts it to kelvin.
TEMPERATURE_TO_KELVIN: dict[str, Callable[[float], float]] = {
    "k": lambda t: t,
    "kelvin": lambda t: t,
    "mk": lambda t: t / 1000.0,
    "c": lambda t: t + 273.15,
    "degc": lambda t: t + 273.15,
    "celsius": lambda t: t + 273.15,
}


class ReadError(Exception):
    """A file could not be turned into valid metadata. The message says why."""


def sha256_of(path: Path, chunk_size: int = 1 << 20) -> str:
    """Checksum of the file bytes, read in chunks so large files use little memory."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def read_metadata(path: Path) -> DatasetMetadata:
    """Extract and validate the metadata of one file, or raise `ReadError`."""
    try:
        with h5py.File(path, "r") as f:
            raw = _extract(f)
    except ReadError:
        raise
    except OSError as exc:
        raise ReadError(f"not a readable HDF5 file ({exc.__class__.__name__})") from exc

    try:
        return DatasetMetadata.model_validate(raw)
    except ValidationError as exc:
        problems = "; ".join(_describe(err["loc"], err["msg"]) for err in exc.errors())
        raise ReadError(f"invalid metadata: {problems}") from exc


def _describe(loc: tuple[int | str, ...], msg: str) -> str:
    """Turn one pydantic error into 'field: problem'."""
    msg = msg.removeprefix("Value error, ")
    return f"{'.'.join(str(part) for part in loc)}: {msg}" if loc else msg


def _extract(f: h5py.File) -> dict[str, Any]:
    entry = find_entry(f)
    instrument = _text(entry, "instrument/name", required=True)
    return {
        "title": _text(entry, "title", required=True),
        "instrument": instrument,
        "technique": _technique(instrument, _text(entry, "definition")),
        "run_number": _value(entry, "entry_identifier", required=True),
        "sample_name": _text(entry, "sample/name", required=True),
        "start_time": _text(entry, "start_time", required=True),
        "end_time": _text(entry, "end_time"),
        "sample_temperature_k": _temperature_k(entry),
        "facility": _text(entry, "instrument/source/name"),
        "proposal_id": _text(entry, "experiment_identifier"),
    }


def find_entry(f: h5py.File) -> h5py.Group:
    for name in ENTRY_NAMES:
        if isinstance(f.get(name), h5py.Group):
            return f[name]
    for item in f.values():
        if isinstance(item, h5py.Group) and _as_str(item.attrs.get("NX_class")) == "NXentry":
            return item
    raise ReadError("no NXentry group found")


def _value(entry: h5py.Group, key: str, *, required: bool = False) -> Any:
    """Return a scalar value as a plain Python object, or None if absent."""
    item = entry.get(key)
    if item is None:
        if required:
            raise ReadError(f"missing field /{entry.name.strip('/')}/{key}")
        return None
    if not isinstance(item, h5py.Dataset):
        raise ReadError(f"/{entry.name.strip('/')}/{key} is a group, not a value")
    value = item[()]
    if isinstance(value, np.ndarray):
        if value.size != 1:
            raise ReadError(f"/{entry.name.strip('/')}/{key} must be a single value")
        value = value.reshape(-1)[0]
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, np.generic):
        return value.item()
    return value


def _text(entry: h5py.Group, key: str, *, required: bool = False) -> str | None:
    value = _value(entry, key, required=required)
    return None if value is None else str(value)


def _as_str(value: object) -> str | None:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return None if value is None else str(value)


def _technique(instrument: str | None, definition: str | None) -> Technique:
    """Look the technique up from the instrument first, then from the definition."""
    if instrument and instrument.strip().upper() in INSTRUMENTS:
        return INSTRUMENTS[instrument.strip().upper()][0]
    if definition in DEFINITION_TECHNIQUE:
        return DEFINITION_TECHNIQUE[definition]
    raise ReadError(
        f"cannot work out the technique (instrument={instrument!r}, definition={definition!r})"
    )


def _temperature_k(entry: h5py.Group) -> float | None:
    value = _value(entry, "sample/temperature")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ReadError("/sample/temperature must be a number")
    units = _as_str(entry["sample/temperature"].attrs.get("units")) or "K"  # NeXus default
    convert = TEMPERATURE_TO_KELVIN.get(units.strip().lower())
    if convert is None:
        raise ReadError(f"unknown temperature unit {units!r}")
    return round(float(convert(value)), 6)

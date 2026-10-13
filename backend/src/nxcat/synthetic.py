"""Synthetic NeXus files for tests and the demo.

Every file is built from a validated `DatasetMetadata`, so valid files are valid
by construction. `Broken` kinds produce deliberately bad files for testing how
ingest handles errors. The same seed always gives the same files.

Command line:  uv run nxcat-generate --out ../data/generated -n 200 --seed 42
"""

import argparse
import random
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

import h5py
import numpy as np

from nxcat.instruments import INSTRUMENTS, TECHNIQUE_DEFINITION
from nxcat.models.metadata import DatasetMetadata

SAMPLES = (
    "benzene",
    "toluene",
    "water",
    "LiFePO4",
    "PEO-LiTFSI",
    "Li7La3Zr2O12",
    "methane hydrate",
    "graphite",
    "CsPbBr3",
    "BMIM-PF6",
)

EARLIEST_START = datetime(2023, 1, 1, tzinfo=UTC)
LATEST_START = datetime(2026, 6, 30, tzinfo=UTC)
N_POINTS = 200  # length of the quick-look spectrum


class Broken(StrEnum):
    """Ways a generated file can be deliberately bad."""

    MISSING_FIELD = "missing_field"  # /entry/title is absent
    WRONG_TYPE = "wrong_type"  # sample temperature is a string
    BAD_VALUE = "bad_value"  # end_time before start_time
    TRUNCATED = "truncated"  # valid HDF5 file cut in half
    NOT_HDF5 = "not_hdf5"  # plain text with a .nxs name


def random_metadata(rng: random.Random, run_number: int) -> DatasetMetadata:
    """Return realistic, valid metadata for one run."""
    instrument = rng.choice(sorted(INSTRUMENTS))
    technique, facility = INSTRUMENTS[instrument]
    sample = rng.choice(SAMPLES)

    span_seconds = int((LATEST_START - EARLIEST_START).total_seconds())
    start = EARLIEST_START + timedelta(seconds=rng.randrange(span_seconds))
    end = start + timedelta(minutes=rng.randint(30, 8 * 60))

    temperature = round(rng.uniform(1.5, 350.0), 1) if rng.random() > 0.1 else None
    title = f"{sample} {technique.value}" + (
        f" {temperature:.0f} K" if temperature is not None else ""
    )

    return DatasetMetadata(
        title=title,
        instrument=instrument,
        technique=technique,
        run_number=run_number,
        sample_name=sample,
        start_time=start,
        end_time=end if rng.random() > 0.05 else None,  # some runs still in progress
        sample_temperature_k=temperature,
        facility=facility,
        proposal_id=str(rng.randint(2_300_000, 2_699_999)),
    )


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def write_nexus(
    path: Path,
    meta: DatasetMetadata,
    rng: random.Random,
    broken: Broken | None = None,
) -> Path:
    """Write `meta` as a NeXus file at `path`, optionally broken on purpose."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if broken is Broken.NOT_HDF5:
        path.write_text("This is not an HDF5 file.\n")
        return path

    with h5py.File(path, "w") as f:
        f.attrs["NX_class"] = "NXroot"
        entry = f.create_group("entry")
        entry.attrs["NX_class"] = "NXentry"

        if broken is not Broken.MISSING_FIELD:
            entry["title"] = meta.title
        entry["definition"] = TECHNIQUE_DEFINITION[meta.technique]
        entry["entry_identifier"] = meta.run_number
        entry["start_time"] = _iso(meta.start_time)
        if broken is Broken.BAD_VALUE:
            entry["end_time"] = _iso(meta.start_time - timedelta(hours=1))
        elif meta.end_time is not None:
            entry["end_time"] = _iso(meta.end_time)
        if meta.proposal_id is not None:
            entry["experiment_identifier"] = meta.proposal_id

        instrument = entry.create_group("instrument")
        instrument.attrs["NX_class"] = "NXinstrument"
        instrument["name"] = meta.instrument
        source = instrument.create_group("source")
        source.attrs["NX_class"] = "NXsource"
        if meta.facility is not None:
            source["name"] = meta.facility

        sample = entry.create_group("sample")
        sample.attrs["NX_class"] = "NXsample"
        sample["name"] = meta.sample_name
        if broken is Broken.WRONG_TYPE:
            sample["temperature"] = "hot"
        elif meta.sample_temperature_k is not None:
            sample["temperature"] = meta.sample_temperature_k
            sample["temperature"].attrs["units"] = "K"

        _write_spectrum(entry, rng)

    if broken is Broken.TRUNCATED:
        data = path.read_bytes()
        path.write_bytes(data[: len(data) // 2])
    return path


def _write_spectrum(entry: h5py.Group, rng: random.Random) -> None:
    """A small peak on a flat background: enough for a quick-look plot.

    Simplification: every technique gets the same energy-transfer axis, even where
    a real instrument would use Q or d-spacing.
    """
    np_rng = np.random.default_rng(rng.randrange(2**32))
    x = np.linspace(-1.0, 1.0, N_POINTS)
    width = np_rng.uniform(0.05, 0.3)
    signal = np.exp(-0.5 * (x / width) ** 2) * np_rng.uniform(50, 500) + np_rng.uniform(1, 10)
    counts = np_rng.poisson(signal).astype(np.float32)

    data = entry.create_group("data")
    data.attrs["NX_class"] = "NXdata"
    data.attrs["signal"] = "counts"
    data.attrs["axes"] = "energy_transfer"
    data["energy_transfer"] = x.astype(np.float32)
    data["energy_transfer"].attrs["units"] = "meV"
    data["counts"] = counts


def generate(
    out_dir: Path,
    n: int,
    seed: int = 42,
    broken: Sequence[Broken] = (),
) -> list[Path]:
    """Write `n` valid files, plus one extra file per entry in `broken`."""
    rng = random.Random(seed)
    first_run = rng.randint(10_000, 90_000)
    paths: list[Path] = []
    kinds: list[Broken | None] = [None] * n + list(broken)
    for i, kind in enumerate(kinds):
        meta = random_metadata(rng, run_number=first_run + i)
        suffix = f"_{kind.value}" if kind is not None else ""
        name = f"{meta.instrument}{meta.run_number:08d}{suffix}.nxs"
        paths.append(write_nexus(out_dir / name, meta, rng, broken=kind))
    return paths


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write synthetic NeXus files.")
    parser.add_argument("--out", type=Path, required=True, help="output folder")
    parser.add_argument("-n", type=int, default=200, help="number of valid files")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--with-broken", action="store_true", help="also write one file of each broken kind"
    )
    args = parser.parse_args(argv)
    if args.n < 0:
        parser.error("-n must not be negative")
    paths = generate(args.out, args.n, args.seed, list(Broken) if args.with_broken else ())
    print(f"Wrote {len(paths)} files to {args.out}")


if __name__ == "__main__":
    main()

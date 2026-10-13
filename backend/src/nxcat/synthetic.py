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
import numpy.typing as npt
from scipy.special import voigt_profile

from nxcat.instruments import INSTRUMENTS, TECHNIQUE_DEFINITION
from nxcat.models.metadata import DatasetMetadata, Technique

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

        if meta.technique is Technique.QENS:
            _write_qens(entry, rng)
        else:
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


# QENS files: a detector-by-energy S(2θ, ω) in the NXSPE layout that qens reads.
QENS_EI_MEV = 3.6  # incident energy, like LET in its high-resolution setting
QENS_RESOLUTION_SIGMA_MEV = 0.0175  # Gaussian resolution (FWHM about 41 µeV)
QENS_ENERGY_EDGES = np.linspace(-1.5, 1.5, 301)  # meV, 300 bins of 10 µeV
QENS_TWO_THETA = np.linspace(10.0, 140.0, 40)  # degrees, one value per detector
HBAR_MEV_PS = 0.65821  # same constant as qens, so Γ = ħ D Q² is consistent
GAUSSIAN_FWHM = 2.3548200450309493  # FWHM divided by sigma, for a Gaussian


def qens_spectra(
    d_a2_per_ps: float, np_rng: np.random.Generator, peak_counts: float = 3000.0
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Simulated counts, errors and Q for Fickian diffusion with coefficient D.

    Each detector sees an elastic line plus a quasi-elastic Lorentzian of
    half-width Γ = ħ D Q², both broadened by the Gaussian resolution, on a flat
    background, with Poisson noise. This is the textbook QENS picture, and it
    gives the analysis a known answer to recover.
    """
    omega = 0.5 * (QENS_ENERGY_EDGES[:-1] + QENS_ENERGY_EDGES[1:])
    ki = np.sqrt(QENS_EI_MEV / 2.0721)  # Å⁻¹, from E = 2.0721 k² for neutrons
    q = 2 * ki * np.sin(np.radians(QENS_TWO_THETA / 2))
    gamma = HBAR_MEV_PS * d_a2_per_ps * q**2
    sigma = QENS_RESOLUTION_SIGMA_MEV
    elastic = voigt_profile(omega[None, :], sigma, 0.0)
    quasi = voigt_profile(omega[None, :], sigma, gamma[:, None])
    eisf = 0.3  # fraction of intensity in the elastic line
    shape = eisf * elastic + (1 - eisf) * quasi
    shape = shape / shape.max(axis=1, keepdims=True)
    expected = peak_counts * shape + 5.0
    counts = np_rng.poisson(expected).astype(np.float64)
    errors = np.sqrt(np.maximum(counts, 1.0))
    return counts, errors, q


def _write_qens(entry: h5py.Group, rng: random.Random) -> None:
    np_rng = np.random.default_rng(rng.randrange(2**32))
    d_true = round(float(np_rng.uniform(0.05, 0.25)), 4)
    counts, errors, _ = qens_spectra(d_true, np_rng)

    # The instrument's energy resolution, as a facility would record it from a
    # vanadium measurement. The analysis uses it instead of guessing from the data.
    resolution = entry["instrument"].create_dataset(
        "energy_resolution", data=round(QENS_RESOLUTION_SIGMA_MEV * GAUSSIAN_FWHM, 6)
    )
    resolution.attrs["units"] = "meV"
    resolution.attrs["description"] = "Gaussian full width at half maximum"

    info = entry.create_group("NXSPE_info")
    info.attrs["NX_class"] = "NXcollection"
    info["fixed_energy"] = QENS_EI_MEV
    info["fixed_energy"].attrs["units"] = "meV"

    data = entry.create_group("data")
    data.attrs["NX_class"] = "NXdata"
    data.attrs["signal"] = "data"
    data.attrs["axes"] = np.array([b"polar", b"energy"])
    data["data"] = counts.astype(np.float32)
    data["error"] = errors.astype(np.float32)
    data["energy"] = QENS_ENERGY_EDGES.astype(np.float32)
    data["energy"].attrs["units"] = "meV"
    data["polar"] = QENS_TWO_THETA.astype(np.float32)
    data["polar"].attrs["units"] = "degrees"
    data["azimuthal"] = np.zeros_like(QENS_TWO_THETA, dtype=np.float32)

    # The value the data was generated with, so an analysis can be checked
    # against it. Real files do not have this; nxcat only shows it if present.
    entry["sample"]["synthetic_diffusion_coefficient"] = d_true
    entry["sample"]["synthetic_diffusion_coefficient"].attrs["units"] = "angstrom^2/ps"


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

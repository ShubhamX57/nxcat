"""Run a qens analysis on one QENS dataset and return the result with provenance.

The scientific work is done by qens (https://github.com/ShubhamX57/qens):

1. `read_nxspe_with_overrides` reads the detector-by-energy S(2θ, ω) and works out Q.
2. `fit_elastic_peak` finds the elastic line and its width.
3. `extract_hwhm` fits elastic + Lorentzian + background in each Q-bin, giving
   the quasi-elastic half-width Γ(Q).
4. The Fickian model from qens, Γ = ħ D Q², is fitted to Γ(Q) to give the
   self-diffusion coefficient D.

nxcat only prepares the inputs, records the settings and software versions, and
stores the result.
"""

import json
import warnings
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Final

import h5py
import numpy as np

METHOD: Final = "qens-fickian"
MIN_Q_BINS = 3


class AnalysisError(Exception):
    """The analysis could not produce a result. The message says why."""


GAUSSIAN_FWHM = 2.3548200450309493  # FWHM divided by sigma, for a Gaussian

ELASTIC_PEAK_WARNING = (
    "No instrument resolution was available, so it was estimated from the dataset's "
    "own elastic peak. Quasi-elastic scattering widens that peak, so D is likely "
    "overestimated (by about 15% on nxcat's synthetic data)."
)


@dataclass(frozen=True)
class Settings:
    q_min: float = 0.3
    q_max: float = 2.5
    energy_window: float = 1.25
    n_q_bins: int = 12
    resolution_fwhm_mev: float | None = None  # overrides what the file records


def qens_provenance() -> dict[str, str | None]:
    """The exact qens version and source commit in use, for the analysis record."""
    dist = metadata.distribution("qens")
    commit = url = None
    try:
        direct = json.loads(dist.read_text("direct_url.json") or "{}")
        commit = direct.get("vcs_info", {}).get("commit_id")
        url = direct.get("url")
    except (json.JSONDecodeError, FileNotFoundError):
        pass
    return {"package": "qens", "version": dist.version, "commit": commit, "source": url}


def _recorded_resolution_fwhm(path: Path) -> float | None:
    """The instrument energy resolution (FWHM, meV) stored in the file, if any."""
    try:
        with h5py.File(path, "r") as f:
            for key in ("entry/instrument/energy_resolution", "entry/instrument/resolution"):
                item = f.get(key)
                if isinstance(item, h5py.Dataset):
                    value = float(item[()])
                    units = item.attrs.get("units", "meV")
                    units = units.decode() if isinstance(units, bytes) else str(units)
                    if value > 0 and units.strip().lower() == "mev":
                        return value
    except (OSError, ValueError, TypeError):
        return None
    return None


def _synthetic_truth(path: Path) -> float | None:
    """The diffusion coefficient a synthetic file was generated with, if any."""
    try:
        with h5py.File(path, "r") as f:
            item = f.get("entry/sample/synthetic_diffusion_coefficient")
            return float(item[()]) if isinstance(item, h5py.Dataset) else None
    except OSError:
        return None


def run_fickian(path: Path, settings: Settings) -> dict[str, Any]:
    """Fit D for one dataset. Raises AnalysisError with a readable reason on failure."""
    import qens
    from scipy.optimize import curve_fit

    try:
        cfg = qens.Config(
            q_min=settings.q_min,
            q_max=settings.q_max,
            energy_window=settings.energy_window,
            n_q_bins=settings.n_q_bins,
        )
    except ValueError as exc:
        raise AnalysisError(f"invalid settings: {exc}") from exc

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            d = qens.read_nxspe_with_overrides(str(path), kind="inc")
        except (KeyError, ValueError, OSError) as exc:
            raise AnalysisError(f"qens could not read the file as NXSPE: {exc}") from exc
        qens.fit_elastic_peak(d)
        # The resolution matters a lot for narrow lines. Best: a value given in the
        # request; next: the instrument resolution recorded in the file; last
        # resort: the dataset's own elastic peak (qens calls this "raw_inc_inflated").
        recorded = _recorded_resolution_fwhm(path)
        if settings.resolution_fwhm_mev is not None:
            d["sigma_res"] = settings.resolution_fwhm_mev / GAUSSIAN_FWHM
            resolution_source = "given in the analysis request"
        elif recorded is not None:
            d["sigma_res"] = recorded / GAUSSIAN_FWHM
            resolution_source = "instrument resolution recorded in the file"
        else:
            d["sigma_res"] = d["sig_raw"]
            resolution_source = "estimated from the dataset's own elastic peak"
        q, hwhm, hwhm_err, eisf = qens.extract_hwhm(d, cfg)
    notes = sorted({str(w.message) for w in caught})
    if resolution_source.startswith("estimated"):
        notes.insert(0, ELASTIC_PEAK_WARNING)

    keep = np.isfinite(hwhm) & np.isfinite(hwhm_err) & (hwhm_err > 0)
    q, hwhm, hwhm_err, eisf = q[keep], hwhm[keep], hwhm_err[keep], eisf[keep]
    if len(q) < MIN_Q_BINS:
        raise AnalysisError(
            f"only {len(q)} Q-bins could be fitted (need at least {MIN_Q_BINS}); "
            "try a wider Q range"
        )

    popt, pcov = curve_fit(
        qens.fickian_hwhm,
        q,
        hwhm,
        p0=[0.1],
        sigma=hwhm_err,
        absolute_sigma=True,
        bounds=(0.0, np.inf),
    )
    d_fit = float(popt[0])
    d_err = float(np.sqrt(pcov[0, 0]))
    residual = (hwhm - qens.fickian_hwhm(q, d_fit)) / hwhm_err
    chi2_red = float(np.sum(residual**2) / max(len(q) - 1, 1))

    return {
        "model": "Fickian diffusion, Γ = ħ D Q²",
        "diffusion_coefficient": round(d_fit, 6),
        "diffusion_coefficient_error": round(d_err, 6),
        "units": "angstrom^2/ps",
        "reduced_chi_squared": round(chi2_red, 3),
        "resolution_fwhm_mev": round(float(d["sigma_res"]) * GAUSSIAN_FWHM, 6),
        "resolution_source": resolution_source,
        "q_bins": [
            {
                "q": round(float(a), 4),
                "hwhm_mev": round(float(b), 6),
                "hwhm_error_mev": round(float(c), 6),
                "eisf": round(float(e), 4),
            }
            for a, b, c, e in zip(q, hwhm, hwhm_err, eisf, strict=True)
        ],
        "synthetic_truth": _synthetic_truth(path),
        "warnings": notes,
    }

import random
from pathlib import Path

import h5py
import pytest

from nxcat.integrations.qens_job import (
    ELASTIC_PEAK_WARNING,
    AnalysisError,
    Settings,
    qens_provenance,
    run_fickian,
)
from nxcat.models.metadata import Technique
from nxcat.synthetic import random_metadata, write_nexus


def qens_file(tmp_path: Path, seed: int = 0, technique: Technique = Technique.QENS) -> Path:
    rng = random.Random(seed)
    while True:
        meta = random_metadata(rng, 1)
        if meta.technique is technique:
            return write_nexus(tmp_path / f"{technique.value}-{seed}.nxs", meta, rng)


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_recovers_the_diffusion_coefficient(tmp_path: Path, seed: int) -> None:
    result = run_fickian(qens_file(tmp_path, seed), Settings())
    truth = result["synthetic_truth"]
    assert truth is not None
    assert result["diffusion_coefficient"] == pytest.approx(truth, rel=0.03)
    assert result["diffusion_coefficient_error"] > 0
    assert result["resolution_source"] == "instrument resolution recorded in the file"
    assert result["resolution_fwhm_mev"] == pytest.approx(0.0412, abs=1e-4)
    assert len(result["q_bins"]) >= 10
    assert result["warnings"] == []


def test_result_lists_q_bins_in_order(tmp_path: Path) -> None:
    bins = run_fickian(qens_file(tmp_path), Settings())["q_bins"]
    qs = [b["q"] for b in bins]
    assert qs == sorted(qs)
    assert all(0.3 <= q <= 2.5 for q in qs)
    assert bins[-1]["hwhm_mev"] > bins[0]["hwhm_mev"]  # Γ grows with Q


def test_resolution_given_in_the_request_wins(tmp_path: Path) -> None:
    result = run_fickian(qens_file(tmp_path), Settings(resolution_fwhm_mev=0.05))
    assert result["resolution_source"] == "given in the analysis request"
    assert result["resolution_fwhm_mev"] == pytest.approx(0.05)


def test_without_a_resolution_it_falls_back_and_warns(tmp_path: Path) -> None:
    path = qens_file(tmp_path)
    with h5py.File(path, "a") as f:
        del f["entry/instrument/energy_resolution"]
    result = run_fickian(path, Settings())
    assert result["resolution_source"] == "estimated from the dataset's own elastic peak"
    assert result["warnings"][0] == ELASTIC_PEAK_WARNING
    assert result["diffusion_coefficient"] > result["synthetic_truth"]  # the known bias


def test_resolution_in_other_units_is_ignored(tmp_path: Path) -> None:
    path = qens_file(tmp_path)
    with h5py.File(path, "a") as f:
        f["entry/instrument/energy_resolution"].attrs["units"] = "ueV"
    assert run_fickian(path, Settings())["resolution_source"].startswith("estimated")


def test_non_nxspe_file_fails_with_a_reason(tmp_path: Path) -> None:
    with pytest.raises(AnalysisError, match="could not read the file as NXSPE"):
        run_fickian(qens_file(tmp_path, technique=Technique.SANS), Settings())


def test_too_narrow_q_range_fails_with_a_reason(tmp_path: Path) -> None:
    with pytest.raises(AnalysisError, match="Q-bins could be fitted"):
        run_fickian(qens_file(tmp_path), Settings(q_min=1.0, q_max=1.05, n_q_bins=12))


def test_invalid_settings_fail_with_a_reason(tmp_path: Path) -> None:
    with pytest.raises(AnalysisError, match="invalid settings"):
        run_fickian(qens_file(tmp_path), Settings(q_min=2.0, q_max=1.0))


def test_provenance_names_the_exact_qens_commit() -> None:
    info = qens_provenance()
    assert info["package"] == "qens"
    assert info["version"]
    assert info["commit"] is not None
    assert len(info["commit"]) == 40
    assert info["source"] == "https://github.com/ShubhamX57/qens"

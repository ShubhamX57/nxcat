import random
from pathlib import Path

import h5py
import numpy as np
import pytest

from nxcat.ingest.reader import ReadError
from nxcat.preview import read_preview
from nxcat.synthetic import N_POINTS, Broken, random_metadata, write_nexus


def make_file(tmp_path: Path, broken: Broken | None = None) -> Path:
    rng = random.Random(11)
    return write_nexus(tmp_path / "run.nxs", random_metadata(rng, 1), rng, broken=broken)


def replace_data(path: Path, **datasets: object) -> None:
    """Rewrite /entry/data with the given datasets ("y" is the signal, "x" the axis)."""
    with h5py.File(path, "a") as f:
        del f["entry/data"]
        data = f["entry"].create_group("data")
        data.attrs["NX_class"] = "NXdata"
        for name, value in datasets.items():
            data[name] = value
        data.attrs["signal"] = "y"
        if "x" in datasets:
            data.attrs["axes"] = "x"


def test_generated_file_previews_with_units(tmp_path: Path) -> None:
    preview = read_preview(make_file(tmp_path))
    assert preview.x_label == "energy_transfer (meV)"
    assert preview.y_label == "counts"
    assert len(preview.x) == len(preview.y) == N_POINTS
    assert preview.original_points == N_POINTS
    assert not preview.downsampled


def test_long_signal_is_binned(tmp_path: Path) -> None:
    path = make_file(tmp_path)
    replace_data(path, x=np.arange(1000.0), y=np.arange(1000.0))
    preview = read_preview(path, max_points=100)
    assert preview.downsampled
    assert preview.original_points == 1000
    assert len(preview.x) == len(preview.y) == 100
    assert preview.y[0] == pytest.approx(4.5)  # mean of 0..9
    assert preview.y[-1] == pytest.approx(994.5)


def test_nan_and_infinity_become_gaps(tmp_path: Path) -> None:
    path = make_file(tmp_path)
    replace_data(path, x=np.arange(4.0), y=np.array([1.0, np.nan, np.inf, 4.0]))
    assert read_preview(path).y == [1.0, None, None, 4.0]


def test_nan_inside_a_bin_is_ignored(tmp_path: Path) -> None:
    path = make_file(tmp_path)
    y = np.array([1.0, np.nan, 3.0, np.nan, np.nan, np.nan])
    replace_data(path, x=np.arange(6.0), y=y)
    preview = read_preview(path, max_points=2)  # bins: [1, nan, 3] and [nan, nan, nan]
    assert preview.y == [2.0, None]


def test_bins_of_only_nan_become_gaps(tmp_path: Path) -> None:
    path = make_file(tmp_path)
    y = np.concatenate([np.ones(20), np.full(20, np.nan)])
    replace_data(path, x=np.arange(40.0), y=y)
    preview = read_preview(path, max_points=10)
    assert preview.y[:5] == [1.0] * 5
    assert preview.y[5:] == [None] * 5


def test_histogram_bin_edges_become_centres(tmp_path: Path) -> None:
    path = make_file(tmp_path)
    replace_data(path, x=np.array([0.0, 2.0, 4.0]), y=np.array([5.0, 7.0]))
    assert read_preview(path).x == [1.0, 3.0]


def test_missing_axis_falls_back_to_index(tmp_path: Path) -> None:
    path = make_file(tmp_path)
    replace_data(path, y=np.array([5.0, 6.0, 7.0]))
    preview = read_preview(path)
    assert preview.x == [0.0, 1.0, 2.0]
    assert preview.x_label == "index"


def test_axis_of_wrong_length_falls_back_to_index(tmp_path: Path) -> None:
    path = make_file(tmp_path)
    replace_data(path, x=np.arange(10.0), y=np.array([5.0, 6.0, 7.0]))
    assert read_preview(path).x_label == "index"


def test_axes_given_as_a_list(tmp_path: Path) -> None:
    path = make_file(tmp_path)
    with h5py.File(path, "a") as f:
        f["entry/data"].attrs["axes"] = np.array([b"energy_transfer"])
    assert read_preview(path).x_label == "energy_transfer (meV)"


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("no_nxdata", "no NXdata group"),
        ("no_signal", "no valid 'signal'"),
        ("three_d", "only 1-D and 2-D signals"),
        ("empty", "the signal is empty"),
        ("text", "cannot read plottable data"),
    ],
)
def test_unplottable_files_give_a_reason(tmp_path: Path, change: str, reason: str) -> None:
    path = make_file(tmp_path)
    if change == "no_nxdata":
        with h5py.File(path, "a") as f:
            del f["entry/data"]
    elif change == "no_signal":
        with h5py.File(path, "a") as f:
            del f["entry/data"].attrs["signal"]
    elif change == "three_d":
        replace_data(path, y=np.ones((2, 3, 3)))
    elif change == "empty":
        replace_data(path, y=np.array([], dtype=float))
    else:
        replace_data(path, y="not numbers")
    with pytest.raises(ReadError, match=reason):
        read_preview(path)


@pytest.mark.parametrize("kind", [Broken.TRUNCATED, Broken.NOT_HDF5])
def test_unreadable_files_give_a_reason(tmp_path: Path, kind: Broken) -> None:
    with pytest.raises(ReadError):
        read_preview(make_file(tmp_path, kind))


def test_two_d_signal_is_summed_over_detectors(tmp_path: Path) -> None:
    path = make_file(tmp_path)
    with h5py.File(path, "a") as f:
        del f["entry/data"]
        data = f["entry"].create_group("data")
        data.attrs["NX_class"] = "NXdata"
        data.attrs["signal"] = "data"
        data.attrs["axes"] = np.array([b"polar", b"energy"])
        data["data"] = np.array([[1.0, 2.0, 3.0], [10.0, 20.0, 30.0]])
        data["polar"] = np.array([10.0, 20.0])
        data["energy"] = np.array([-1.0, 0.0, 1.0, 2.0])  # bin edges
        data["energy"].attrs["units"] = "meV"
    preview = read_preview(path)
    assert preview.y == [11.0, 22.0, 33.0]
    assert preview.x == [-0.5, 0.5, 1.5]
    assert preview.x_label == "energy (meV)"
    assert preview.y_label == "data, sum of 2 spectra"


def test_generated_qens_file_previews_as_one_spectrum(tmp_path: Path) -> None:
    rng = random.Random(0)
    while True:
        meta = random_metadata(rng, 1)
        if meta.technique.value == "QENS":
            break
    preview = read_preview(write_nexus(tmp_path / "q.nxs", meta, rng))
    assert preview.x_label == "energy (meV)"
    assert len(preview.y) == 300
    assert preview.y_label == "data, sum of 40 spectra"

import random
from datetime import datetime
from pathlib import Path

import h5py
import pytest

from nxcat.models.metadata import DatasetMetadata
from nxcat.synthetic import (
    INSTRUMENTS,
    N_POINTS,
    Broken,
    generate,
    main,
    random_metadata,
    write_nexus,
)


def read_text(f: h5py.File, key: str) -> str:
    value: str = f[key].asstr()[()]
    return value


def one_file(tmp_path: Path, broken: Broken | None = None) -> tuple[Path, DatasetMetadata]:
    rng = random.Random(1)
    meta = random_metadata(rng, run_number=12345)
    return write_nexus(tmp_path / "run.nxs", meta, rng, broken=broken), meta


def test_metadata_is_valid_and_consistent() -> None:
    rng = random.Random(0)
    for run in range(200):
        meta = random_metadata(rng, run_number=run)
        technique, facility = INSTRUMENTS[meta.instrument]
        assert meta.technique is technique
        assert meta.facility == facility


def test_same_seed_gives_same_files(tmp_path: Path) -> None:
    first = generate(tmp_path / "a", n=5, seed=7)
    second = generate(tmp_path / "b", n=5, seed=7)
    assert [p.name for p in first] == [p.name for p in second]
    for a, b in zip(first, second, strict=True):
        with h5py.File(a) as fa, h5py.File(b) as fb:
            assert read_text(fa, "entry/title") == read_text(fb, "entry/title")
            assert (fa["entry/data/counts"][()] == fb["entry/data/counts"][()]).all()


def test_different_seeds_give_different_files(tmp_path: Path) -> None:
    first = generate(tmp_path / "a", n=5, seed=1)
    second = generate(tmp_path / "b", n=5, seed=2)
    assert [p.name for p in first] != [p.name for p in second]


def test_valid_file_contains_the_metadata(tmp_path: Path) -> None:
    path, meta = one_file(tmp_path)
    with h5py.File(path) as f:
        assert read_text(f, "entry/title") == meta.title
        assert read_text(f, "entry/instrument/name") == meta.instrument
        assert read_text(f, "entry/sample/name") == meta.sample_name
        assert f["entry/entry_identifier"][()] == meta.run_number
        assert datetime.fromisoformat(read_text(f, "entry/start_time")) == meta.start_time
        assert f["entry"].attrs["NX_class"] == "NXentry"
        assert f["entry/data/counts"].shape == (N_POINTS,)
        if meta.sample_temperature_k is not None:
            assert f["entry/sample/temperature"][()] == pytest.approx(meta.sample_temperature_k)
            assert f["entry/sample/temperature"].attrs["units"] == "K"


def test_generate_writes_n_files_with_unique_names(tmp_path: Path) -> None:
    paths = generate(tmp_path, n=20)
    assert len(paths) == 20
    assert len({p.name for p in paths}) == 20
    assert all(p.stat().st_size < 50_000 for p in paths)


def test_generate_adds_one_file_per_broken_kind(tmp_path: Path) -> None:
    paths = generate(tmp_path, n=3, broken=list(Broken))
    assert len(paths) == 3 + len(Broken)
    for kind in Broken:
        assert any(p.stem.endswith(kind.value) for p in paths)


def test_missing_field(tmp_path: Path) -> None:
    path, _ = one_file(tmp_path, Broken.MISSING_FIELD)
    with h5py.File(path) as f:
        assert "title" not in f["entry"]


def test_wrong_type(tmp_path: Path) -> None:
    path, _ = one_file(tmp_path, Broken.WRONG_TYPE)
    with h5py.File(path) as f:
        assert read_text(f, "entry/sample/temperature") == "hot"


def test_bad_value(tmp_path: Path) -> None:
    path, _ = one_file(tmp_path, Broken.BAD_VALUE)
    with h5py.File(path) as f:
        start = datetime.fromisoformat(read_text(f, "entry/start_time"))
        end = datetime.fromisoformat(read_text(f, "entry/end_time"))
    assert end < start


@pytest.mark.parametrize("kind", [Broken.TRUNCATED, Broken.NOT_HDF5])
def test_unreadable_files_cannot_be_opened(tmp_path: Path, kind: Broken) -> None:
    path, _ = one_file(tmp_path, kind)
    with pytest.raises(OSError):
        h5py.File(path)


def test_cli_writes_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["--out", str(tmp_path), "-n", "4", "--with-broken"])
    assert len(list(tmp_path.glob("*.nxs"))) == 4 + len(Broken)
    assert "Wrote 9 files" in capsys.readouterr().out


def test_cli_rejects_negative_n(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["--out", str(tmp_path), "-n", "-1"])

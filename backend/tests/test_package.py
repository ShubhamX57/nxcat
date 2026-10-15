import tomllib
from pathlib import Path

import nxcat

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_package_version_matches_pyproject() -> None:
    """The installed package reports the version written in pyproject.toml.

    Comparing with pyproject (not a fixed string) means a version bump only has to
    be made in one place.
    """
    expected = tomllib.loads(PYPROJECT.read_text())["project"]["version"]
    assert nxcat.__version__ == expected

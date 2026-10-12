import nxcat


def test_package_exposes_version() -> None:
    assert nxcat.__version__ == "0.0.1"

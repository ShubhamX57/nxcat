"""Quick-look data for one NeXus file: the main 1-D signal against its axis.

NeXus marks the data to plot with an NXdata group whose `signal` attribute names
the y values and whose `axes` attribute names the x values. Long signals are
reduced to at most `max_points` by averaging equal-width bins, so the browser
never receives millions of points.
"""

from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

import h5py
import numpy as np
import numpy.typing as npt

from nxcat.ingest.reader import ReadError, find_entry

DEFAULT_MAX_POINTS = 500


@dataclass(frozen=True)
class Preview:
    x: list[float | None]
    y: list[float | None]
    x_label: str
    y_label: str
    original_points: int
    downsampled: bool


def read_preview(path: Path, max_points: int = DEFAULT_MAX_POINTS) -> Preview:
    """Read the plottable signal of `path`, or raise `ReadError` explaining why not."""
    try:
        with h5py.File(path, "r") as f:
            data = _find_nxdata(find_entry(f))
            signal_name = _attr(data, "signal")
            if signal_name is None or not isinstance(data.get(signal_name), h5py.Dataset):
                raise ReadError("the NXdata group has no valid 'signal' attribute")
            signal = data[signal_name]
            y = np.asarray(signal[()], dtype=float)
            x_name, x = _axis(data, len(y) if y.ndim == 1 else -1)
            y_label = _label(signal_name, signal)
            x_label = _label(x_name, data[x_name]) if x_name else "index"
    except ReadError:
        raise
    except (OSError, ValueError, TypeError) as exc:
        raise ReadError(f"cannot read plottable data ({exc.__class__.__name__})") from exc

    if y.ndim != 1:
        raise ReadError(f"only 1-D signals can be previewed (this one is {y.ndim}-D)")
    if len(y) == 0:
        raise ReadError("the signal is empty")

    original = len(y)
    xs, ys = (x, y) if original <= max_points else (_bin(x, max_points), _bin(y, max_points))
    return Preview(
        x=_finite(xs),
        y=_finite(ys),
        x_label=x_label,
        y_label=y_label,
        original_points=original,
        downsampled=original > max_points,
    )


def _find_nxdata(entry: h5py.Group) -> h5py.Group:
    candidates = [entry.get("data"), *entry.values()]
    for item in candidates:
        if isinstance(item, h5py.Group) and _attr(item, "NX_class") == "NXdata":
            return item
    raise ReadError("no NXdata group to plot")


def _axis(data: h5py.Group, length: int) -> tuple[str | None, npt.NDArray[np.float64]]:
    """The x axis named by `axes`, or 0, 1, 2, ... if there is no usable one."""
    axes = data.attrs.get("axes")
    if isinstance(axes, np.ndarray | list) and len(axes) > 0:
        axes = axes[0]
    name = axes.decode() if isinstance(axes, bytes) else axes
    if isinstance(name, str) and isinstance(data.get(name), h5py.Dataset):
        values = np.asarray(data[name][()], dtype=float)
        if values.ndim == 1 and len(values) == length:
            return name, values
        if values.ndim == 1 and len(values) == length + 1:  # histogram bin edges
            return name, (values[:-1] + values[1:]) / 2
    return None, np.arange(max(length, 0), dtype=float)


def _attr(obj: h5py.HLObject, key: str) -> str | None:
    value = obj.attrs.get(key)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return None if value is None else str(value)


def _label(name: str, dataset: h5py.Dataset) -> str:
    units = _attr(dataset, "units")
    return f"{name} ({units})" if units else name


def _bin(values: npt.NDArray[np.float64], n_bins: int) -> npt.NDArray[np.float64]:
    """Mean of `n_bins` equal-width groups. NaNs are ignored inside each bin."""
    edges = np.linspace(0, len(values), n_bins + 1).astype(int)
    with np.errstate(invalid="ignore"):
        return np.array(
            [
                np.nanmean(chunk) if np.isfinite(chunk).any() else np.nan
                for chunk in (values[a:b] for a, b in pairwise(edges))
            ]
        )


def _finite(values: npt.NDArray[np.float64]) -> list[float | None]:
    """JSON has no NaN or infinity, so those become null (a gap in the plot)."""
    return [float(v) if np.isfinite(v) else None for v in values]

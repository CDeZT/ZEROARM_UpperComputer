"""Fast binary STL loading for the validated runtime robot model."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class MeshGeometry:
    link_name: str
    triangles: NDArray[np.float32]
    bounds_min: tuple[float, float, float]
    bounds_max: tuple[float, float, float]


_TRIANGLE_DTYPE = np.dtype(
    [("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attribute", "<u2")]
)


def load_binary_stl(path: Path, *, link_name: str) -> MeshGeometry:
    with path.open("rb") as stream:
        stream.seek(80)
        count = int(np.fromfile(stream, dtype="<u4", count=1)[0])
        records = np.fromfile(stream, dtype=_TRIANGLE_DTYPE, count=count)
    if len(records) != count or path.stat().st_size != 84 + count * 50:
        raise ValueError(f"invalid binary STL: {path.name}")
    triangles = np.ascontiguousarray(records["vertices"], dtype=np.float32)
    if not np.isfinite(triangles).all() or not len(triangles):
        raise ValueError(f"STL contains no finite triangles: {path.name}")
    flat = triangles.reshape(-1, 3)
    minimum = tuple(float(value) for value in flat.min(axis=0))
    maximum = tuple(float(value) for value in flat.max(axis=0))
    return MeshGeometry(link_name, triangles, minimum, maximum)  # type: ignore[arg-type]

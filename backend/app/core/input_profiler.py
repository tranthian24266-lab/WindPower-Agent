from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


class InputProfileError(RuntimeError):
    """Raised when an uploaded diagnosis input cannot be inspected safely."""


@dataclass(frozen=True)
class InputProfile:
    filename: str
    suffix: str
    size_bytes: int
    container_type: str
    columns: list[str] = field(default_factory=list)
    sampled_row_count: int | None = None
    numeric_column_count: int | None = None
    array_shape: list[int] | None = None
    array_dtype: str | None = None
    array_keys: list[str] = field(default_factory=list)
    array_shapes: dict[str, list[int]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class InputProfilerService:
    def profile(self, path: Path) -> InputProfile:
        resolved = Path(path)
        if not resolved.is_file():
            raise InputProfileError(f"Input file does not exist: {resolved}")
        suffix = resolved.suffix.lower()
        if suffix == ".csv":
            return self._profile_csv(resolved)
        if suffix == ".npy":
            return self._profile_npy(resolved)
        if suffix == ".npz":
            return self._profile_npz(resolved)
        if suffix == ".mat":
            return self._profile_mat(resolved)
        raise InputProfileError(f"Unsupported input type for automatic diagnosis: {suffix}")

    def _profile_csv(self, path: Path) -> InputProfile:
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle)
                header = next(reader, None)
                if not header:
                    raise InputProfileError("CSV input is empty or has no header row.")
                columns = [str(value).strip() for value in header]
                sample_rows: list[list[str]] = []
                for _, row in zip(range(25), reader):
                    sample_rows.append(row)
        except UnicodeDecodeError as exc:
            raise InputProfileError("CSV input must be UTF-8 encoded.") from exc

        numeric_count = 0
        for index in range(len(columns)):
            values = [row[index].strip() for row in sample_rows if index < len(row) and row[index].strip()]
            if values and all(_is_number(value) for value in values):
                numeric_count += 1
        return InputProfile(
            filename=path.name,
            suffix=path.suffix.lower(),
            size_bytes=path.stat().st_size,
            container_type="tabular",
            columns=columns,
            sampled_row_count=len(sample_rows),
            numeric_column_count=numeric_count,
        )

    def _profile_npy(self, path: Path) -> InputProfile:
        try:
            array = np.load(path, mmap_mode="r", allow_pickle=False)
        except Exception as exc:
            raise InputProfileError(f"Failed to inspect NPY input: {exc}") from exc
        return InputProfile(
            filename=path.name,
            suffix=path.suffix.lower(),
            size_bytes=path.stat().st_size,
            container_type="numeric_array",
            array_shape=[int(value) for value in array.shape],
            array_dtype=str(array.dtype),
        )

    def _profile_npz(self, path: Path) -> InputProfile:
        try:
            with np.load(path, allow_pickle=False) as archive:
                keys = list(archive.files)
                shapes = {key: [int(value) for value in archive[key].shape] for key in keys}
        except Exception as exc:
            raise InputProfileError(f"Failed to inspect NPZ input: {exc}") from exc
        return InputProfile(
            filename=path.name,
            suffix=path.suffix.lower(),
            size_bytes=path.stat().st_size,
            container_type="numeric_archive",
            array_keys=keys,
            array_shapes=shapes,
        )

    def _profile_mat(self, path: Path) -> InputProfile:
        try:
            from scipy.io import whosmat

            variables = whosmat(path)
        except Exception as exc:
            raise InputProfileError(f"Failed to inspect MAT input: {exc}") from exc
        keys = [str(name) for name, _, _ in variables]
        shapes = {str(name): [int(value) for value in shape] for name, shape, _ in variables}
        return InputProfile(
            filename=path.name,
            suffix=path.suffix.lower(),
            size_bytes=path.stat().st_size,
            container_type="matlab",
            array_keys=keys,
            array_shapes=shapes,
        )


def _is_number(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True

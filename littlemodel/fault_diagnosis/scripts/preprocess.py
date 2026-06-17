from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.io import loadmat


WINDOW_SIZE = 4096
DEFAULT_STRIDE = 4096


def zscore_window(window: np.ndarray) -> np.ndarray:
    window = window.astype(np.float32, copy=False)
    return (window - window.mean()) / (window.std() + 1e-8)


def _flatten_numeric(value: Any) -> np.ndarray:
    array = np.asarray(value)
    if array.dtype == object:
        if array.size == 0:
            return np.asarray([], dtype=np.float64)
        if array.size == 1:
            return _flatten_numeric(array.reshape(-1)[0])
        raise ValueError("Unsupported object array with multiple elements.")
    return np.ravel(array)


def _load_signal_from_mat(input_path: Path, channel_candidates: list[str]) -> tuple[np.ndarray, str]:
    mat_data = loadmat(input_path, squeeze_me=True, struct_as_record=False)
    visible = {key: value for key, value in mat_data.items() if not key.startswith("__")}
    for channel in channel_candidates:
        if channel in visible:
            signal = _flatten_numeric(visible[channel]).astype(np.float32, copy=False)
            return signal, channel
    raise ValueError(
        f"None of the expected channels were found in {input_path.name}. "
        f"Expected one of {channel_candidates}, available keys: {sorted(visible.keys())}"
    )


def _load_signal_from_csv(input_path: Path) -> np.ndarray:
    df = pd.read_csv(input_path)
    numeric = df.select_dtypes(include=["number"])
    if numeric.empty:
        raise ValueError(f"No numeric columns found in {input_path.name}.")

    if numeric.shape[1] == 1:
        return numeric.iloc[:, 0].to_numpy(dtype=np.float32)
    if numeric.shape[1] == WINDOW_SIZE:
        return numeric.to_numpy(dtype=np.float32)

    raise ValueError(
        "CSV input must be either a single numeric signal column or a table with exactly 4096 numeric columns."
    )


def _load_signal_from_npy(input_path: Path) -> np.ndarray:
    return np.load(input_path)


def _windows_from_1d(signal: np.ndarray, window_size: int, stride: int) -> np.ndarray:
    signal = np.asarray(signal, dtype=np.float32).reshape(-1)
    if signal.size < window_size:
        raise ValueError(f"Signal length {signal.size} is shorter than required window size {window_size}.")
    windows = [zscore_window(signal[start : start + window_size]) for start in range(0, signal.size - window_size + 1, stride)]
    if not windows:
        raise ValueError("No windows could be generated from the input signal.")
    return np.stack(windows, axis=0)[:, None, :]


def _coerce_windows(array: np.ndarray, window_size: int, stride: int) -> np.ndarray:
    array = np.asarray(array, dtype=np.float32)
    if array.ndim == 1:
        return _windows_from_1d(array, window_size=window_size, stride=stride)
    if array.ndim == 2:
        if array.shape[1] == window_size:
            windows = np.stack([zscore_window(row) for row in array], axis=0)
            return windows[:, None, :]
        if array.shape[0] == window_size:
            return _windows_from_1d(array.reshape(-1), window_size=window_size, stride=stride)
    if array.ndim == 3 and array.shape[1] == 1 and array.shape[2] == window_size:
        windows = np.stack([zscore_window(row[0]) for row in array], axis=0)
        return windows[:, None, :]
    raise ValueError("Unsupported array shape. Expected raw 1D signal or windows shaped [N, 4096] / [N, 1, 4096].")


def load_windows(
    input_path: str | Path,
    channel_candidates: list[str],
    window_size: int = WINDOW_SIZE,
    stride: int = DEFAULT_STRIDE,
) -> tuple[np.ndarray, dict[str, Any]]:
    input_path = Path(input_path)
    suffix = input_path.suffix.lower()
    metadata: dict[str, Any] = {"input_format": suffix}

    if suffix == ".mat":
        signal, channel = _load_signal_from_mat(input_path, channel_candidates)
        metadata["selected_channel"] = channel
        windows = _windows_from_1d(signal, window_size=window_size, stride=stride)
    elif suffix == ".csv":
        array = _load_signal_from_csv(input_path)
        windows = _coerce_windows(array, window_size=window_size, stride=stride)
    elif suffix == ".npy":
        array = _load_signal_from_npy(input_path)
        windows = _coerce_windows(array, window_size=window_size, stride=stride)
    else:
        raise ValueError(f"Unsupported input format: {suffix}. Supported formats: .mat, .csv, .npy")

    metadata["num_windows"] = int(windows.shape[0])
    metadata["window_size"] = int(window_size)
    metadata["stride"] = int(stride)
    return windows.astype(np.float32), metadata

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats
from scipy.io import loadmat
from scipy.signal import stft


DEFAULT_FS = 97656
DEFAULT_NPERSEG = 128
DEFAULT_NOVERLAP = 64


def _flatten_numeric(value: Any) -> np.ndarray:
    array = np.asarray(value)
    if array.dtype == object:
        if array.size == 0:
            return np.asarray([], dtype=np.float64)
        if array.size == 1:
            return _flatten_numeric(array.reshape(-1)[0])
        raise ValueError("Object array contains multiple elements and cannot be flattened safely.")
    return np.ravel(array)


def load_vibration_signal(input_path: str | Path, signal_key: str = "vibration") -> tuple[np.ndarray, dict[str, Any]]:
    input_path = Path(input_path)
    if input_path.suffix.lower() != ".mat":
        raise ValueError(
            f"Unsupported input format: {input_path.suffix}. "
            "This packaged RUL model currently supports only .mat inputs with a 'vibration' variable."
        )

    mat_data = loadmat(input_path, squeeze_me=True, struct_as_record=False)
    if signal_key not in mat_data:
        visible_keys = sorted([key for key in mat_data.keys() if not key.startswith("__")])
        raise KeyError(
            f"Missing required variable '{signal_key}' in {input_path.name}. "
            f"Available variables: {visible_keys}"
        )

    vibration = _flatten_numeric(mat_data[signal_key]).astype(np.float64, copy=False)
    if vibration.size == 0:
        raise ValueError(f"Variable '{signal_key}' is empty in {input_path.name}.")
    if np.isnan(vibration).any() or np.isinf(vibration).any():
        raise ValueError(f"Variable '{signal_key}' contains NaN or Inf in {input_path.name}.")

    metadata = {
        "input_format": ".mat",
        "signal_key": signal_key,
        "signal_length": int(vibration.size),
    }
    return vibration, metadata


def compute_spectral_kurtosis(
    signal: np.ndarray,
    fs: int = DEFAULT_FS,
    nperseg: int = DEFAULT_NPERSEG,
    noverlap: int = DEFAULT_NOVERLAP,
) -> tuple[np.ndarray, np.ndarray]:
    freqs, _, zxx = stft(
        signal,
        fs=fs,
        nperseg=nperseg,
        noverlap=noverlap,
        detrend=False,
        boundary=None,
        padded=False,
    )
    abs_z = np.abs(zxx)
    m2 = np.mean(abs_z**2, axis=1)
    m4 = np.mean(abs_z**4, axis=1)
    sk = m4 / (m2**2 + 1e-12) - 2.0
    return freqs, sk


def _safe_skew(array: np.ndarray) -> float:
    if np.std(array) < 1e-12:
        return 0.0
    return float(stats.skew(array, bias=False))


def _safe_kurtosis(array: np.ndarray) -> float:
    if np.std(array) < 1e-12:
        return 0.0
    return float(stats.kurtosis(array, fisher=False, bias=False))


def compute_traditional_features(signal: np.ndarray) -> OrderedDict[str, float]:
    return OrderedDict(
        [
            ("mean", float(np.mean(signal))),
            ("std", float(np.std(signal))),
            ("skewness", _safe_skew(signal)),
            ("kurtosis", _safe_kurtosis(signal)),
            ("peak_to_peak", float(np.ptp(signal))),
            ("rms", float(np.sqrt(np.mean(signal**2)))),
        ]
    )


def compute_sk_features(
    signal: np.ndarray,
    fs: int = DEFAULT_FS,
    nperseg: int = DEFAULT_NPERSEG,
    noverlap: int = DEFAULT_NOVERLAP,
) -> tuple[OrderedDict[str, float], np.ndarray, np.ndarray]:
    freqs, sk_curve = compute_spectral_kurtosis(signal, fs=fs, nperseg=nperseg, noverlap=noverlap)
    features = OrderedDict(
        [
            ("sk_mean", float(np.mean(sk_curve))),
            ("sk_std", float(np.std(sk_curve))),
            ("sk_skewness", _safe_skew(sk_curve)),
            ("sk_kurtosis", _safe_kurtosis(sk_curve)),
            ("sk_peak_to_peak", float(np.ptp(sk_curve))),
            ("sk_area", float(np.trapezoid(sk_curve, freqs))),
            ("sk_area_positive", float(np.trapezoid(np.maximum(sk_curve, 0.0), freqs))),
            ("sk_max", float(np.max(sk_curve))),
        ]
    )
    return features, freqs, sk_curve


def compute_all_features(
    signal: np.ndarray,
    fs: int = DEFAULT_FS,
    nperseg: int = DEFAULT_NPERSEG,
    noverlap: int = DEFAULT_NOVERLAP,
) -> tuple[OrderedDict[str, float], dict[str, Any]]:
    traditional = compute_traditional_features(signal)
    sk_features, freqs, sk_curve = compute_sk_features(signal, fs=fs, nperseg=nperseg, noverlap=noverlap)
    features = OrderedDict()
    features.update(traditional)
    features.update(sk_features)
    metadata = {
        "sampling_rate_hz": int(fs),
        "stft_nperseg": int(nperseg),
        "stft_noverlap": int(noverlap),
        "sk_curve_length": int(sk_curve.shape[0]),
        "sk_freq_bins": int(freqs.shape[0]),
    }
    return features, metadata

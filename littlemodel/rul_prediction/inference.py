from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import joblib
import numpy as np
import pandas as pd
import yaml

CURRENT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = CURRENT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from feature_extraction import compute_all_features, load_vibration_signal


MODEL_ID = "hssb_svr_multifeature_60_40"
MODEL_NAME = "HSSB SVR Multi-feature RUL Prediction Model"
MODEL_VERSION = "1.0.0"
WEIGHT_FILENAME = "svr_demo_multifeature_60_40.joblib"


def _load_config() -> dict[str, Any]:
    with (CURRENT_DIR / "config.yaml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    return value


def _load_payload() -> dict[str, Any]:
    weight_path = CURRENT_DIR / "weights" / WEIGHT_FILENAME
    if not weight_path.exists():
        raise FileNotFoundError(f"Missing required weight file: {weight_path}")
    payload = joblib.load(weight_path)
    if not isinstance(payload, dict) or "model" not in payload or "feature_names" not in payload:
        raise ValueError(f"Unexpected joblib payload structure in {weight_path.name}.")
    return payload


def _risk_level(rul_raw: float, config: dict[str, Any]) -> str:
    critical_max = float(config["inference"]["risk_thresholds"]["critical_max"])
    warning_max = float(config["inference"]["risk_thresholds"]["warning_max"])
    if rul_raw <= critical_max:
        return "critical"
    if rul_raw <= warning_max:
        return "warning"
    return "normal"


def predict(input_path: str, output_dir: str, options: dict | None = None) -> dict:
    options = options or {}
    config = _load_config()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        signal, input_meta = load_vibration_signal(
            input_path=input_path,
            signal_key=options.get("signal_key", config["inference"]["mat_signal_key"]),
        )
        features_all, feature_meta = compute_all_features(
            signal=signal,
            fs=int(config["feature_extraction"]["sampling_rate_hz"]),
            nperseg=int(config["feature_extraction"]["stft_nperseg"]),
            noverlap=int(config["feature_extraction"]["stft_noverlap"]),
        )

        payload = _load_payload()
        model = payload["model"]
        feature_names = list(payload["feature_names"])
        missing = [name for name in feature_names if name not in features_all]
        if missing:
            raise ValueError(f"Missing required extracted features: {missing}")

        feature_vector = np.asarray([[features_all[name] for name in feature_names]], dtype=np.float64)
        rul_raw = float(model.predict(feature_vector)[0])
        clip_min, clip_max = config["inference"]["clipped_range"]
        rul_clipped = float(np.clip(rul_raw, float(clip_min), float(clip_max)))
        selected_features = {name: float(features_all[name]) for name in feature_names}
        risk_level = _risk_level(rul_raw=rul_raw, config=config)

        result = {
            "task_type": "rul_prediction",
            "model_id": MODEL_ID,
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
            "status": "success",
            "input_file": str(Path(input_path).resolve()),
            "rul_raw": rul_raw,
            "rul_clipped": rul_clipped,
            "rul_unit": config["inference"]["rul_unit"],
            "risk_level": risk_level,
            "features": selected_features,
            "summary": (
                f"Extracted {len(feature_names)} training-aligned features from one HSSB vibration record and "
                f"predicted raw RUL {rul_raw:.3f}."
            ),
            "recommendation": (
                "Immediate inspection is recommended because the predicted remaining life is very low."
                if risk_level == "critical"
                else "Increase monitoring frequency and review recent degradation trend."
                if risk_level == "warning"
                else "Continue monitoring and compare with later measurements in the same run-to-failure sequence."
            ),
            "preprocess": {
                "input": input_meta,
                "feature_extraction": feature_meta,
                "feature_order": feature_names,
            },
            "artifacts": {},
        }

        feature_csv = output_path / "feature.csv"
        pd.DataFrame([{name: float(features_all[name]) for name in features_all.keys()}]).to_csv(feature_csv, index=False)

        result_json = output_path / "result.json"
        result["artifacts"] = {
            "result_json": str(result_json),
            "feature_csv": str(feature_csv),
        }
        result_json.write_text(json.dumps(_json_safe(result), indent=2, ensure_ascii=False), encoding="utf-8")
        return _json_safe(result)
    except Exception as exc:
        failed = {
            "status": "failed",
            "error": str(exc),
            "task_type": "rul_prediction",
        }
        (output_path / "result.json").write_text(json.dumps(failed, indent=2, ensure_ascii=False), encoding="utf-8")
        return failed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to one HSSB .mat measurement file")
    parser.add_argument("--output", required=True, help="Output directory for inference artifacts")
    args = parser.parse_args()
    result = predict(args.input, args.output)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
import torch
import yaml

CURRENT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = CURRENT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from model import create_model, get_batch_size


MODEL_ID = "scada_ae_decoder_transfer_13_to_10"
MODEL_NAME = "SCADA Autoencoder Transfer Anomaly Detection Model"
MODEL_VERSION = "1.0.0"
WEIGHT_FILENAME = "best_anomaly_model.pt"


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


def _load_checkpoint(device: torch.device) -> dict[str, Any]:
    weight_path = CURRENT_DIR / "weights" / WEIGHT_FILENAME
    if not weight_path.exists():
        raise FileNotFoundError(f"Missing required weight file: {weight_path}")
    # This checkpoint is a trusted local artifact and intentionally stores scaler + metadata objects.
    # Do not reuse this loading path for arbitrary user-uploaded checkpoints.
    checkpoint = torch.load(weight_path, map_location=device, weights_only=False)
    required = {"input_dim", "feature_cols", "scaler", "threshold", "state_dict"}
    missing = required.difference(checkpoint.keys())
    if missing:
        raise ValueError(f"Checkpoint missing required fields: {sorted(missing)}")
    return checkpoint


def _load_input_table(input_path: str | Path, feature_names: list[str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    input_path = Path(input_path)
    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(input_path)
    elif suffix == ".npy":
        array = np.load(input_path)
        array = np.asarray(array, dtype=np.float64)
        if array.ndim == 1:
            if array.shape[0] != len(feature_names):
                raise ValueError(f"1D .npy input must have length {len(feature_names)}, got {array.shape[0]}.")
            array = array.reshape(1, -1)
        if array.ndim != 2 or array.shape[1] != len(feature_names):
            raise ValueError(
                f".npy input must have shape [N, {len(feature_names)}] or [{len(feature_names)}], got {array.shape}."
            )
        frame = pd.DataFrame(array, columns=feature_names)
    else:
        raise ValueError(f"Unsupported input format: {suffix}. Supported formats: .csv, .npy")

    missing = [column for column in feature_names if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required feature columns: {missing}")

    metadata = {
        "input_format": suffix,
        "num_rows": int(len(frame)),
        "num_columns": int(len(frame.columns)),
    }
    return frame, metadata


def _risk_level(anomaly_ratio: float, config: dict[str, Any]) -> str:
    critical_min = float(config["inference"]["risk_thresholds"]["critical_min_ratio"])
    warning_min = float(config["inference"]["risk_thresholds"]["warning_min_ratio"])
    if anomaly_ratio >= critical_min:
        return "critical"
    if anomaly_ratio >= warning_min:
        return "warning"
    return "normal"


def predict(input_path: str, output_dir: str, options: dict | None = None) -> dict:
    options = options or {}
    config = _load_config()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        device = torch.device("cuda" if torch.cuda.is_available() and options.get("device") != "cpu" else "cpu")
        checkpoint = _load_checkpoint(device=device)
        feature_names = list(checkpoint["feature_cols"])
        frame, input_meta = _load_input_table(input_path=input_path, feature_names=feature_names)

        scaler = checkpoint["scaler"]
        model = create_model(input_dim=int(checkpoint["input_dim"]))
        model.load_state_dict(checkpoint["state_dict"])
        model.to(device)
        model.eval()

        selected = frame[feature_names].copy()
        selected = selected.apply(pd.to_numeric, errors="coerce")
        if selected.isna().any().any():
            selected = selected.fillna(0.0)
        scaled = scaler.transform(selected.to_numpy(dtype=np.float64)).astype(np.float32)

        batch_size = int(options.get("batch_size", get_batch_size(len(feature_names))))
        all_scores: list[np.ndarray] = []
        for start in range(0, len(scaled), batch_size):
            batch = torch.tensor(scaled[start : start + batch_size], device=device)
            with torch.no_grad():
                reconstructed = model(batch)
                squared_error = torch.mean((batch - reconstructed) ** 2, dim=1)
                rmse = torch.sqrt(squared_error)
            all_scores.append(rmse.cpu().numpy())
        scores = np.concatenate(all_scores, axis=0) if all_scores else np.asarray([], dtype=np.float32)

        threshold = float(checkpoint["threshold"])
        predictions = (scores >= threshold).astype(int)
        labels = np.where(predictions == 1, "anomaly", "normal")
        num_anomalies = int(predictions.sum())
        anomaly_ratio = float(num_anomalies / len(predictions)) if len(predictions) else 0.0
        risk_level = _risk_level(anomaly_ratio=anomaly_ratio, config=config)

        prediction_frame = frame.copy()
        prediction_frame["anomaly_score"] = scores.astype(float)
        prediction_frame["prediction"] = predictions.astype(int)
        prediction_frame["pred_label"] = labels.tolist()
        prediction_csv = output_path / "prediction.csv"
        prediction_frame.to_csv(prediction_csv, index=False)

        result = {
            "task_type": "anomaly_detection",
            "model_id": MODEL_ID,
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
            "status": "success",
            "input_file": str(Path(input_path).resolve()),
            "threshold": threshold,
            "num_samples": int(len(predictions)),
            "num_anomalies": num_anomalies,
            "anomaly_ratio": anomaly_ratio,
            "mean_anomaly_score": float(scores.mean()) if len(scores) else 0.0,
            "max_anomaly_score": float(scores.max()) if len(scores) else 0.0,
            "risk_level": risk_level,
            "summary": (
                f"Scored {len(predictions)} samples with RMSE reconstruction error and found "
                f"{num_anomalies} samples above threshold."
            ),
            "recommendation": (
                "Escalate inspection for the target turbine because the anomaly ratio is high."
                if risk_level == "critical"
                else "Review flagged samples and compare with recent SCADA trends."
                if risk_level == "warning"
                else "Continue monitoring; most samples remain below the anomaly threshold."
            ),
            "preprocess": {
                "input": input_meta,
                "feature_order": feature_names,
                "normalization": config["inference"]["normalization"],
                "score_name": config["inference"]["score_name"],
            },
            "artifacts": {},
        }

        result_json = output_path / "result.json"
        result["artifacts"] = {
            "result_json": str(result_json),
            "prediction_csv": str(prediction_csv),
        }
        result_json.write_text(json.dumps(_json_safe(result), indent=2, ensure_ascii=False), encoding="utf-8")
        return _json_safe(result)
    except Exception as exc:
        failed = {
            "status": "failed",
            "error": str(exc),
            "task_type": "anomaly_detection",
        }
        (output_path / "result.json").write_text(json.dumps(failed, indent=2, ensure_ascii=False), encoding="utf-8")
        return failed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to one SCADA .csv or .npy input file")
    parser.add_argument("--output", required=True, help="Output directory for inference artifacts")
    args = parser.parse_args()
    result = predict(args.input, args.output)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())

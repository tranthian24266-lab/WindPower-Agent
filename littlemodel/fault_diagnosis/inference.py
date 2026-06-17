from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import yaml

CURRENT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = CURRENT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from model import MSCNNBiLSTM
from preprocess import load_windows


MODEL_ID = "nrel_binary_mscnn_bilstm_sensor1"
MODEL_NAME = "NREL Binary MSCNN-BiLSTM Fault Diagnosis Model"
MODEL_VERSION = "1.0.0"
CLASS_NAMES = ["healthy", "damaged"]
WEIGHT_FILENAME = "sensor1_mscnn_bilstm_binary_best.pth"


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


def _load_model(device: torch.device, config: dict[str, Any]) -> MSCNNBiLSTM:
    weight_path = CURRENT_DIR / "weights" / WEIGHT_FILENAME
    if not weight_path.exists():
        raise FileNotFoundError(f"Missing required weight file: {weight_path}")
    model = MSCNNBiLSTM(
        input_channels=1,
        scales=config["model"]["scales"],
        lstm_hidden=config["model"]["lstm_hidden"],
        lstm_layers=config["model"]["lstm_layers"],
        dropout=config["model"]["dropout"],
        num_classes=len(CLASS_NAMES),
    )
    checkpoint = torch.load(weight_path, map_location=device, weights_only=True)
    state_dict = checkpoint["model_state_dict"] if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint else checkpoint
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    return model


def _risk_level(prediction: str, confidence: float) -> str:
    if prediction == "damaged":
        return "warning" if confidence < 0.9 else "critical"
    return "normal"


def predict(input_path: str, output_dir: str, options: dict | None = None) -> dict:
    options = options or {}
    config = _load_config()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        channel_candidates = options.get("channel_candidates") or config["preprocess"]["mat_channel_candidates"]
        stride = int(options.get("stride", config["preprocess"]["stride"]))
        windows, preprocess_meta = load_windows(
            input_path=input_path,
            channel_candidates=channel_candidates,
            window_size=int(config["preprocess"]["window_size"]),
            stride=stride,
        )

        device = torch.device("cuda" if torch.cuda.is_available() and options.get("device") != "cpu" else "cpu")
        model = _load_model(device=device, config=config)

        with torch.no_grad():
            inputs = torch.from_numpy(windows).to(device)
            logits = model(inputs)
            probabilities = torch.softmax(logits, dim=1).cpu().numpy()

        window_predictions = probabilities.argmax(axis=1)
        mean_probabilities = probabilities.mean(axis=0)
        class_id = int(np.argmax(mean_probabilities))
        prediction = CLASS_NAMES[class_id]
        confidence = float(mean_probabilities[class_id])
        class_probabilities = {name: float(mean_probabilities[idx]) for idx, name in enumerate(CLASS_NAMES)}

        result = {
            "task_type": "fault_diagnosis",
            "model_id": MODEL_ID,
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
            "status": "success",
            "input_file": str(Path(input_path).resolve()),
            "prediction": prediction,
            "class_id": class_id,
            "confidence": confidence,
            "class_probabilities": class_probabilities,
            "risk_level": _risk_level(prediction, confidence),
            "summary": f"Aggregated {int(windows.shape[0])} windows from sensor1-compatible input and predicted {prediction}.",
            "recommendation": (
                "Inspect the gearbox and collect more diagnostic evidence."
                if prediction == "damaged"
                else "Continue monitoring under the current maintenance schedule."
            ),
            "preprocess": preprocess_meta,
            "artifacts": {},
        }

        prediction_rows = pd.DataFrame(
            {
                "window_index": np.arange(len(window_predictions)),
                "predicted_class_id": window_predictions.astype(int),
                "predicted_label": [CLASS_NAMES[idx] for idx in window_predictions],
                "prob_healthy": probabilities[:, 0].astype(float),
                "prob_damaged": probabilities[:, 1].astype(float),
            }
        )
        prediction_csv = output_path / "prediction.csv"
        prediction_rows.to_csv(prediction_csv, index=False)

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
            "task_type": "fault_diagnosis",
        }
        (output_path / "result.json").write_text(json.dumps(failed, indent=2, ensure_ascii=False), encoding="utf-8")
        return failed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to .mat, .csv, or .npy input")
    parser.add_argument("--output", required=True, help="Output directory for inference artifacts")
    args = parser.parse_args()
    result = predict(args.input, args.output)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())

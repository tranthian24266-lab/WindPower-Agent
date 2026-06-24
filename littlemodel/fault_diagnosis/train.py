from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from runtime_common import append_log, ensure_runtime_dirs, format_traceback, relpath_str, reset_log, write_json

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import inference


DEFAULT_INPUT = MODULE_DIR / "test_data" / "test_sensor1_x.npy"
DEFAULT_LABELS = MODULE_DIR / "test_data" / "test_y.npy"


def evaluate_checkpoint(input_path: Path, labels_path: Path) -> dict:
    ensure_runtime_dirs(MODULE_DIR)
    output_dir = MODULE_DIR / "outputs"
    log_path = MODULE_DIR / "logs" / "fault_diagnosis_run.log"
    reset_log(log_path, "fault_diagnosis train/eval wrapper")
    append_log(log_path, f"Evaluating packaged checkpoint with input={input_path} labels={labels_path}")
    append_log(
        log_path,
        "This wrapper evaluates the packaged MSCNN-BiLSTM checkpoint on preserved test windows. "
        "It does not retrain the upstream deep-learning-fault-diagnosis PCA-CNN project because that source repo is not vendored here.",
    )

    config = inference._load_config()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = inference._load_model(device=device, config=config)
    windows = np.load(input_path).astype(np.float32)
    labels = np.load(labels_path).astype(int)

    with torch.no_grad():
        logits = model(torch.from_numpy(windows).to(device))
        probabilities = torch.softmax(logits, dim=1).cpu().numpy()
    predictions = probabilities.argmax(axis=1)

    accuracy = float(accuracy_score(labels, predictions))
    macro_f1 = float(f1_score(labels, predictions, average="macro"))
    matrix = confusion_matrix(labels, predictions, labels=[0, 1])
    class_probs = {
        "healthy_mean_probability": float(probabilities[:, 0].mean()),
        "damaged_mean_probability": float(probabilities[:, 1].mean()),
    }

    metrics = {
        "accuracy": accuracy,
        "f1_score": macro_f1,
        "num_samples": int(len(labels)),
        **class_probs,
    }
    metrics_path = output_dir / "metrics.json"
    write_json(metrics_path, metrics)

    fig, ax = plt.subplots(figsize=(4.5, 4))
    im = ax.imshow(matrix, cmap="Blues")
    ax.set_xticks([0, 1], labels=["healthy", "damaged"])
    ax.set_yticks([0, 1], labels=["healthy", "damaged"])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("Fault Diagnosis Confusion Matrix")
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            ax.text(col, row, int(matrix[row, col]), ha="center", va="center", color="black")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    confusion_path = output_dir / "confusion_matrix.png"
    fig.savefig(confusion_path, dpi=160)
    plt.close(fig)

    summary = {
        "module": "fault_diagnosis",
        "model_name": "NREL Binary MSCNN-BiLSTM Fault Diagnosis Model",
        "data_source": "packaged_test_data",
        "input_file": str(input_path),
        "status": "success",
        "metrics": {
            "accuracy": accuracy,
            "f1_score": macro_f1,
        },
        "artifacts": {
            "checkpoint": relpath_str(MODULE_DIR / "weights" / inference.WEIGHT_FILENAME, MODULE_DIR),
            "confusion_matrix": relpath_str(confusion_path, MODULE_DIR),
            "metrics": relpath_str(metrics_path, MODULE_DIR),
            "log": relpath_str(log_path, MODULE_DIR),
        },
        "error": None,
    }
    write_json(output_dir / "summary.json", summary)
    append_log(log_path, f"Evaluation metrics: {metrics}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to packaged test windows (.npy)")
    parser.add_argument("--labels", default=str(DEFAULT_LABELS), help="Path to labels (.npy)")
    args = parser.parse_args()

    try:
        summary = evaluate_checkpoint(input_path=Path(args.input), labels_path=Path(args.labels))
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        log_path = MODULE_DIR / "logs" / "fault_diagnosis_run.log"
        append_log(log_path, format_traceback(exc))
        failed = {
            "module": "fault_diagnosis",
            "model_name": "NREL Binary MSCNN-BiLSTM Fault Diagnosis Model",
            "data_source": "packaged_test_data",
            "input_file": args.input,
            "status": "fail",
            "metrics": {"accuracy": None, "f1_score": None},
            "artifacts": {"log": relpath_str(log_path, MODULE_DIR)},
            "error": str(exc),
        }
        write_json(MODULE_DIR / "outputs" / "summary.json", failed)
        print(json.dumps(failed, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

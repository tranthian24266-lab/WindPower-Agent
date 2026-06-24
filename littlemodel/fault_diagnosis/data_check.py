from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from runtime_common import append_log, ensure_runtime_dirs, format_traceback, reset_log, write_json


MODULE_DIR = Path(__file__).resolve().parent
HF_DATASET_ID = "alidi/wind-turbine-5mw-bearing-dataset"
ZENODO_URL = "https://doi.org/10.5281/zenodo.7674842"


def check_hf_access() -> dict:
    try:
        from huggingface_hub import HfApi
    except Exception as exc:
        return {
            "status": "fail",
            "mode": "package_missing",
            "message": f"huggingface_hub is not installed: {exc}",
        }

    api = HfApi()
    try:
        info = api.dataset_info(HF_DATASET_ID)
        return {
            "status": "success",
            "mode": "anonymous",
            "message": f"Anonymous access succeeded for dataset {HF_DATASET_ID}.",
            "id": getattr(info, "id", HF_DATASET_ID),
        }
    except Exception as anonymous_exc:
        token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
        if token:
            try:
                info = HfApi(token=token).dataset_info(HF_DATASET_ID)
                return {
                    "status": "success",
                    "mode": "token",
                    "message": f"Token-authenticated access succeeded for dataset {HF_DATASET_ID}.",
                    "id": getattr(info, "id", HF_DATASET_ID),
                }
            except Exception as token_exc:
                return {
                    "status": "fail",
                    "mode": "token_failed",
                    "message": (
                        f"Anonymous access failed with: {anonymous_exc}. "
                        f"Token-authenticated access also failed with: {token_exc}."
                    ),
                }

        return {
            "status": "fail",
            "mode": "anonymous_failed",
            "message": (
                f"Anonymous access failed with: {anonymous_exc}. "
                "Run `huggingface-cli login` or set `HF_TOKEN`, otherwise fall back to the Zenodo mirror."
            ),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()

    ensure_runtime_dirs(MODULE_DIR)
    log_path = MODULE_DIR / "logs" / "fault_diagnosis_run.log"
    summary_path = MODULE_DIR / "outputs" / "data_check_summary.json"
    reset_log(log_path, "fault_diagnosis data_check")

    try:
        access_report = check_hf_access()
        append_log(log_path, f"HuggingFace access report: {access_report}")
        append_log(log_path, f"Zenodo fallback URL: {ZENODO_URL}")
        append_log(
            log_path,
            "Current littlemodel package exposes an MSCNN-BiLSTM deployment artifact. "
            "The upstream PCA-CNN training repository is not vendored under this module yet.",
        )
        payload = {
            "status": "success" if access_report["status"] == "success" else "fail",
            "dataset_id": HF_DATASET_ID,
            "zenodo_fallback": ZENODO_URL,
            "report": access_report,
            "error": None if access_report["status"] == "success" else access_report["message"],
        }
        write_json(summary_path, payload)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload["status"] == "success" else 1
    except Exception as exc:
        append_log(log_path, format_traceback(exc))
        payload = {
            "status": "fail",
            "dataset_id": HF_DATASET_ID,
            "zenodo_fallback": ZENODO_URL,
            "report": {},
            "error": str(exc),
        }
        write_json(summary_path, payload)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

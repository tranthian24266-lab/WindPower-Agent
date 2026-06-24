# README_little_models

This file tracks the current repo-local runnable state for the three wind-power small-model modules under `littlemodel/`.

## Current Status

### 1. anomaly_detection

- Status: `已跑通`
- Module path: `littlemodel/anomaly_detection`
- Data source: CARE2Compare-style SCADA CSV sample packaged in `test_data/test_data_sample.csv`
- Current model: `SCADA Autoencoder Transfer Anomaly Detection Model`
- Platform readiness: suitable for an initial platform demo now

Run commands:

```bash
cd littlemodel/anomaly_detection
python data_check.py
python smoke_test.py
python train.py
python predict.py --input test_data/test_data_sample.csv
```

Input format:

- One CARE2Compare-like `.csv`
- Default preprocessing expects `Avg / average / mean` style columns
- `Min / Max / Std` style columns are excluded by default unless `--include_stats_cols` is passed

Output files:

- `logs/health_detection_run.log`
- `outputs/prepared_input.csv`
- `outputs/anomaly_scores.csv`
- `outputs/anomaly_plot.png`
- `outputs/summary.json`
- `outputs/predict/predict_result.json`

Current notes:

- The minimal wrapper uses the packaged checkpoint rather than refitting a new EnergyFaultDetector model.
- This is still enough for a first unified platform-callable demo.

### 2. fault_diagnosis

- Status: `部分跑通`
- Module path: `littlemodel/fault_diagnosis`
- Data source:
  - packaged evaluation data in `test_data/`
  - upstream external access target: HuggingFace dataset `alidi/wind-turbine-5mw-bearing-dataset`
- Current model: `NREL Binary MSCNN-BiLSTM Fault Diagnosis Model`
- Platform readiness: inference/eval demo is ready; upstream PCA-CNN training integration is not ready yet

Run commands:

```bash
cd littlemodel/fault_diagnosis
python data_check.py
python smoke_test.py
python train.py
python predict.py --input test_data/test_sensor1_x.npy
```

Input format:

- `.npy`, `.csv`, or `.mat`
- Current packaged smoke path uses `test_data/test_sensor1_x.npy`

Output files:

- `logs/fault_diagnosis_run.log`
- `outputs/metrics.json`
- `outputs/confusion_matrix.png`
- `outputs/summary.json`
- `outputs/predict/predict_result.json`

Current notes:

- `data_check.py` confirmed anonymous HuggingFace access at run time in this environment.
- The repo-local packaged model is not the requested `deep-learning-fault-diagnosis / PCA-CNN` upstream project.
- `train.py` currently evaluates the packaged MSCNN-BiLSTM checkpoint instead of retraining the PCA-CNN project.

### 3. rul_prediction

- Status: `已跑通`
- Module path: `littlemodel/rul_prediction`
- Data source: packaged `WindTurbineHighSpeedBearingPrognosis-Data` `.mat` files in `test_data/`
- Current model: `HSSB SVR Multi-feature RUL Prediction Model`
- Platform readiness: suitable for an initial platform demo now

Run commands:

```bash
cd littlemodel/rul_prediction
python data_check.py
python smoke_test.py
python train.py
python predict.py --input test_data/split_60_40/data-20130406T221209Z.mat
```

Input format:

- `.mat` with a `vibration` variable

Output files:

- `logs/rul_data_check.log`
- `logs/rul_hsb_run.log`
- `outputs/degradation_features.csv`
- `outputs/health_indicator.png`
- `outputs/rul_or_degradation_metrics.json`
- `outputs/summary.json`
- `outputs/predict/predict_result.json`

Current notes:

- The minimal baseline path is intentionally not the original GRU notebook chain.
- `train.py` now proves data reading, feature extraction, and degradation-trend visualization over an ordered split.

## Unified Predict Interface

Each module now exposes:

```bash
python predict.py --input <path>
```

The wrapper writes a unified JSON payload shaped like:

```json
{
  "module": "",
  "model_name": "",
  "input_file": "",
  "status": "success/fail",
  "prediction": {
    "fault_class": null,
    "fault_probability": null,
    "health_score": null,
    "is_anomaly": null,
    "anomaly_score": null,
    "rul": null
  },
  "artifacts": {},
  "error": null
}
```

## Main Gaps

- `anomaly_detection`: still uses the packaged checkpoint demo instead of in-repo retraining.
- `fault_diagnosis`: the external PCA-CNN project is not yet vendored or wrapped as a controllable in-repo training workflow.
- `rul_prediction`: the original notebook has not yet been converted into a robust in-repo training pipeline; the current baseline is the packaged SVR path plus degradation trend generation.

## Platform Integration Recommendation

- First priority: `anomaly_detection`
  - Best fit for immediate platform demo because it now has single-file input, logging, summary output, plot output, and unified predict JSON.
- Second priority: `rul_prediction`
  - Good demo candidate because it has stable packaged `.mat` input plus meaningful trend artifacts.
- Third priority: `fault_diagnosis`
  - Current inference/eval wrapper is usable, but the upstream project mismatch should be resolved before calling it the final target module.

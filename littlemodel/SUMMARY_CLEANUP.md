# SUMMARY_CLEANUP

## Default Models Kept

- `fault_diagnosis`: `sensor1_mscnn_bilstm_binary_best.pth`
- `rul_prediction`: `svr_demo_multifeature_60_40.joblib`
- `anomaly_detection`: `best_anomaly_model.pt`

## Directory Layout

- `fault_diagnosis/`: README, model card, config, inference entrypoint, weight, test arrays, example runner, model/preprocess scripts, docs, optional non-default artifacts
- `rul_prediction/`: README, model card, config, inference entrypoint, default joblib payload, preserved MAT test data, example runner, feature extraction script, docs, optional non-default SVR models
- `anomaly_detection/`: README, model card, config, self-contained inference entrypoint, default AE checkpoint, preserved CSV sample data, example runner, AE model script, docs

## Input / Output Summary

- `fault_diagnosis`: input `.mat`, `.csv`, or `.npy`; output binary `healthy` or `damaged` prediction plus probabilities and `prediction.csv`
- `rul_prediction`: input `.mat` with `vibration`; output `rul_raw`, `rul_clipped`, selected features, and `feature.csv`
- `anomaly_detection`: input `.csv` or `.npy` with 55 SCADA features; output anomaly statistics and per-sample `prediction.csv`

## Backup / Cleanup Notes

- Existing pre-cleanup backups remain in `_backup_before_cleanup/`
- Non-default RUL and fault-diagnosis model artifacts remain outside default `weights/` in `optional_models/`
- No new destructive deletion was performed during this pass

## Manual Follow-up

- None required for feature-name recovery: the anomaly checkpoint contained the full 55-feature list
- RUL packaged inference currently supports the `.mat` vibration format from the local training code only

## Example Commands

```bash
cd C:\Users\luzian\Desktop\littlemodel
python fault_diagnosis\examples\run_example.py
python rul_prediction\examples\run_example.py
python anomaly_detection\examples\run_example.py
```

## Platform Entrypoints

- `fault_diagnosis/inference.py:predict`
- `rul_prediction/inference.py:predict`
- `anomaly_detection/inference.py:predict`

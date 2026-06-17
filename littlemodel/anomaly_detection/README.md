# anomaly_detection

This package exposes the default SCADA autoencoder transfer-learning anomaly detector in a platform-friendly structure. The packaged default is the decoder-tuning checkpoint `best_anomaly_model.pt` for source turbine `13` to target turbine `10`.

## Scope

- Task type: anomaly detection
- Model type: fully connected autoencoder
- Method: decoder tuning transfer learning
- Input dimension: `55` SCADA features
- Anomaly score: RMSE reconstruction error

## Input

- Supported formats:
  - `.csv` with all required 55 SCADA feature columns
  - `.npy` shaped `[N, 55]` or `[55]`
- Feature order is fixed and stored in both `config.yaml` and the trusted checkpoint metadata.
- The packaged inference path uses the `MinMaxScaler` stored inside the checkpoint. It does not refit a new scaler.

## Output

`inference.py:predict` returns a JSON-serializable dict with:

- `threshold`
- `num_samples`
- `num_anomalies`
- `anomaly_ratio`
- `mean_anomaly_score`
- `max_anomaly_score`
- `risk_level`
- `artifacts.result_json`
- `artifacts.prediction_csv`

`prediction.csv` contains one row per sample with `anomaly_score`, `prediction`, and `pred_label`.

## Files

- `weights/`: default deployed checkpoint only
- `test_data/`: preserved SCADA sample input
- `scripts/model.py`: self-contained autoencoder definition
- `docs/`: paper, local reproduction guide, original README, and original metadata snapshot

## Run

```bash
python inference.py --input test_data/test_data_sample.csv --output examples/outputs
python examples/run_example.py
```

## Notes

- Input must provide the 55 SCADA features listed in `config.yaml`.
- `anomaly_score` is the autoencoder RMSE reconstruction error.
- Samples with `anomaly_score >= 0.04287222` are labeled as anomalies.
- Threshold, source turbine, target turbine, and published local metrics were recovered from the packaged checkpoint metadata.

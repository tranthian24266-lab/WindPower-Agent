# rul_prediction

This package exposes the default HSSB remaining useful life demo model in a platform-friendly structure. The packaged default is `svr_demo_multifeature_60_40.joblib` because it delivered the best raw MAE and RMSE among the locally reproduced candidate models.

## Scope

- Task type: remaining useful life prediction
- Model type: `sklearn` SVR pipeline serialized with `joblib`
- Intended use: demo-scale paper reproduction on a single run-to-failure sequence
- Not intended use: engineering-grade fleet lifetime estimation

## Input

- Stable packaged input format: `.mat`
- Required MAT variable: `vibration`
- Auxiliary MAT variable `tach` may exist in the dataset, but the packaged inference path only needs `vibration`
- Feature extraction follows the local training code:
  - traditional features: `mean`, `std`, `skewness`, `kurtosis`, `peak_to_peak`, `rms`
  - spectral kurtosis features: `sk_mean`, `sk_std`, `sk_skewness`, `sk_kurtosis`, `sk_peak_to_peak`, `sk_area`, `sk_area_positive`, `sk_max`
- Default deployed SVR feature order:
  - `sk_area_positive`
  - `kurtosis`
  - `std`
  - `peak_to_peak`

## Output

`inference.py:predict` returns a JSON-serializable dict with:

- `rul_raw`: primary model output
- `rul_clipped`: clipped display-safe output only
- `risk_level`: `normal`, `warning`, or `critical`
- `features`: the exact selected feature values used by the default SVR model
- `artifacts.result_json`
- `artifacts.feature_csv`

## Files

- `weights/`: default deployed SVR payload only
- `optional_models/`: other reproduced SVR variants kept outside the default deployment path
- `test_data/`: preserved `.mat` measurement files
- `docs/`: paper, feature tables, metrics summary, and reproduction summary
- `scripts/feature_extraction.py`: training-aligned feature extraction logic

## Run

```bash
python inference.py --input test_data/split_60_40/data-20130406T221209Z.mat --output examples/outputs
python examples/run_example.py
```

## Notes

- This is a small RUL demo/reproduction package based on one degradation trajectory.
- Raw RUL is the main output. Clipped RUL is retained only for safer platform display.
- Other non-default SVR models were preserved in `optional_models/` and are not the platform default.

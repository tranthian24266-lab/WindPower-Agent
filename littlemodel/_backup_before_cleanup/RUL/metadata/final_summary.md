# Final Summary

## 1. Dataset
- Data path: `C:\Users\luzian\Desktop\windpower_dataset\RUL\WindTurbineHighSpeedBearingPrognosis-Data`
- File count: `50`
- Sampling rate: `97656 Hz`

## 2. Feature Extraction
- Traditional features: mean, std, skewness, kurtosis, peak_to_peak, rms.
- Spectral Kurtosis implementation: STFT-based approximation using scipy.signal.stft.
- SK-derived features: sk_mean, sk_std, sk_skewness, sk_kurtosis, sk_peak_to_peak, sk_area, sk_area_positive, sk_max.
- RUL label definition: `rul = np.arange(N - 1, -1, -1)` so the last measurement has RUL 0.

## 3. Train/Test Strategy
- Split type 1: first 60% train, last 40% test.
- Split type 2: first 40% train, last 60% test.
- No random shuffling was used anywhere in the pipeline.
- StandardScaler and hyperparameter search were fitted only on the training subset of each experiment.
- Original paper-style reproduction experiments use single-feature `sk_area + SVR` or `kurtosis + SVR` inputs.
- Additional demo models use multi-feature inputs to improve demo stability under the single-run dataset limitation.

## 4. Runtime Environment
- Python executable: `C:\Users\luzian\.conda\envs\pytorch\python.exe`
- Torch version: `2.8.0+cu129`
- CUDA available: `True`
- CUDA device: `NVIDIA GeForce RTX 5070 Laptop GPU`
- Note: SVR is an sklearn model and therefore runs on CPU even though CUDA availability was checked in the pytorch environment.

## 5. SVR Hyperparameters and Results
### kurtosis_baseline_60_40
- Feature used: `kurtosis`
- Train/Test sizes: `30/20`
- Best params: `{'svr__C': 1000, 'svr__epsilon': 0.5, 'svr__gamma': 0.001, 'svr__kernel': 'rbf'}`
- Best CV score (neg RMSE): `-8.722847`
- Test raw MAE/RMSE/R2: `8.115564` / `10.030232` / `-2.025731`
- Test clipped MAE/RMSE/R2: `8.020060` / `10.021134` / `-2.020244`
- Model file: `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\models\svr_kurtosis_baseline_60_40.joblib`
- Prediction file: `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\reports\predictions_kurtosis_baseline_60_40.csv`

### area_sk_60_40
- Feature used: `sk_area`
- Train/Test sizes: `30/20`
- Best params: `{'svr__C': 1000, 'svr__epsilon': 0.5, 'svr__gamma': 0.001, 'svr__kernel': 'rbf'}`
- Best CV score (neg RMSE): `-9.437221`
- Test raw MAE/RMSE/R2: `9.385016` / `10.833348` / `-2.529667`
- Test clipped MAE/RMSE/R2: `5.983469` / `7.365133` / `-0.631434`
- Model file: `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\models\svr_area_sk_60_40.joblib`
- Prediction file: `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\reports\predictions_area_sk_60_40.csv`

### area_sk_40_60
- Feature used: `sk_area`
- Train/Test sizes: `20/30`
- Best params: `{'svr__C': 100, 'svr__epsilon': 0.01, 'svr__gamma': 0.001, 'svr__kernel': 'rbf'}`
- Best CV score (neg RMSE): `-7.091663`
- Test raw MAE/RMSE/R2: `17.597953` / `18.151264` / `-3.397798`
- Test clipped MAE/RMSE/R2: `17.597953` / `18.151264` / `-3.397798`
- Model file: `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\models\svr_area_sk_40_60.joblib`
- Prediction file: `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\reports\predictions_area_sk_40_60.csv`

### demo_multifeature_svr_60_40
- Feature used: `sk_area_positive,kurtosis,std,peak_to_peak`
- Train/Test sizes: `30/20`
- Best params: `{'svr__C': 1000, 'svr__epsilon': 0.5, 'svr__gamma': 0.001, 'svr__kernel': 'rbf'}`
- Best CV score (neg RMSE): `-7.853521`
- Test raw MAE/RMSE/R2: `5.567151` / `6.487603` / `-0.265834`
- Test clipped MAE/RMSE/R2: `5.136010` / `6.169532` / `-0.144756`
- Model file: `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\models\svr_demo_multifeature_60_40.joblib`
- Prediction file: `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\reports\predictions_demo_multifeature_60_40.csv`

### demo_sk_multi_linear_40_60
- Feature used: `sk_area,sk_area_positive,sk_max,sk_std,sk_peak_to_peak,sk_mean`
- Train/Test sizes: `20/30`
- Best params: `{'svr__C': 10, 'svr__epsilon': 0.05, 'svr__kernel': 'linear'}`
- Best CV score (neg RMSE): `-5.552367`
- Test raw MAE/RMSE/R2: `7.278679` / `9.289813` / `-0.151955`
- Test clipped MAE/RMSE/R2: `4.770453` / `5.942087` / `0.528698`
- Model file: `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\models\svr_demo_sk_multi_linear_40_60.joblib`
- Prediction file: `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\reports\predictions_demo_sk_multi_linear_40_60.csv`

## 6. Generated Artifacts
- Features: `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\features\all_features.csv`
- Models:
  - `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\models\svr_area_sk_40_60.joblib`
  - `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\models\svr_area_sk_60_40.joblib`
  - `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\models\svr_demo_multifeature_60_40.joblib`
  - `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\models\svr_demo_sk_multi_linear_40_60.joblib`
  - `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\models\svr_kurtosis_baseline_60_40.joblib`
- Figures:
  - `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\figures\fig_feature_trends.png`
  - `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\figures\fig_monotonicity_trendability.png`
  - `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\figures\fig_svr_fit_kurtosis_vs_area_sk.png`
  - `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\figures\fig_rul_prediction_area_sk_60_40.png`
  - `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\figures\fig_rul_prediction_area_sk_40_60.png`
  - `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\figures\fig_rul_prediction_demo_multifeature_60_40.png`
  - `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\figures\fig_rul_prediction_demo_sk_multi_linear_40_60.png`
- Metrics summary: `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\reports\metrics_summary.csv`
- Reproduction log: `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\reports\reproduction_log.txt`

## 7. Differences From the Original Paper
- The paper does not provide a full SVR hyperparameter table, so this reproduction uses TimeSeriesSplit-based grid search on the training subset.
- The original work is based on spectral kurtosis / kurtogram ideas; this Python reproduction uses an STFT-based spectral kurtosis approximation.
- Trendability is traditionally more meaningful across multiple run-to-failure units. Here only one degradation trajectory is available, so trendability is approximated by the absolute correlation between feature value and time index.
- CUDA availability was checked inside the pytorch environment, but the reproduced SVR pipeline itself is an sklearn CPU workflow.
- Clipped RUL is used only for engineering protection and demo visualization. It does not replace the raw metrics for the original paper-style reproduction experiments.
- The current dataset contains only one 50-point run-to-failure sequence, so the trained models should be treated as a paper reproduction and demo-scale small model rather than an engineering-grade RUL model.

## 8. Cleanup
- Cleanup completed: `yes`
- Removed items:
  - `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\_tmp`
  - `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\__pycache__`
  - `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\src\__pycache__`
  - `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\features\traditional_features.csv`
  - `C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction\outputs\features\sk_features.csv`

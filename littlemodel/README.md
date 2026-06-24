# littlemodel

This directory is a normalized small-model library for three wind-power tasks:

- `fault_diagnosis`: NREL healthy vs damaged fault diagnosis with the default sensor1 MSCNN-BiLSTM checkpoint
- `rul_prediction`: HSSB remaining useful life demo with the default multi-feature SVR payload
- `anomaly_detection`: SCADA transfer-learning anomaly detection with the default decoder-tuning autoencoder checkpoint

## Structure

Each model directory follows the same deployment-oriented layout:

```text
model_folder/
  README.md
  model_card.json
  config.yaml
  inference.py
  requirements.txt
  weights/
  test_data/
  examples/
  scripts/
```

## Registry

Use `model_registry.json` to discover the default active model for each task. Every active model exposes the same adapter entrypoint pattern:

```text
inference.py:predict
```

The platform can resolve a model by `task_type`, locate `model_dir`, import the corresponding `inference.py`, and call:

```python
predict(input_path: str, output_dir: str, options: dict | None = None) -> dict
```

## Run One Model

```bash
cd C:\Users\luzian\Desktop\littlemodel
python fault_diagnosis\examples\run_example.py
python rul_prediction\examples\run_example.py
python anomaly_detection\examples\run_example.py
```

## Validation

```bash
cd C:\Users\luzian\Desktop\littlemodel
python validate_model_library.py
python run_all_examples.py
```

## Minimal Runtime Wrappers

For the current repo-local runnable wrappers, see `README_little_models.md`. It summarizes:

- `data_check.py`
- `smoke_test.py`
- `train.py`
- `predict.py`

for each module, plus the current integration gaps between the packaged demo models and their upstream reproduction projects.

## Add a Model Package

See [`MODEL_PACKAGE_MANUAL.md`](MODEL_PACKAGE_MANUAL.md) for the required ZIP structure, file responsibilities, `model_card.json` schema, unified `predict()` contract, validation rules, publication flow, and archive/delete safeguards.

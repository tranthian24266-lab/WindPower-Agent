# fault_diagnosis

This package exposes the default NREL binary fault diagnosis model in a platform-friendly structure. It is a `healthy` vs `damaged` binary classifier only, not a multi-fault classifier. The default deployed model is the sensor1 MSCNN-BiLSTM checkpoint because it achieved the strongest test performance in the local reproduction (`Accuracy=0.9775`, `Macro-F1=0.977489`).

## Input

- Default task type: gearbox fault diagnosis
- Supported formats:
  - `.mat`: raw signal file containing a sensor1-compatible channel. Inference prefers `AN9` and falls back to `AN8`.
  - `.csv`: either one numeric signal column or a 4096-column pre-windowed table.
  - `.npy`: raw 1D signal, `[N, 4096]`, or `[N, 1, 4096]`.
- Preprocessing:
  - window size: `4096`
  - stride: `4096`
  - normalization: per-window z-score

## Output

`inference.py:predict` returns a JSON-serializable dict with the task type, model id, final binary label, class id, confidence, aggregated class probabilities, risk level, and artifact paths. It also writes:

- `result.json`
- `prediction.csv`

## Files

- `weights/`: default sensor1 checkpoint only
- `optional_models/`: non-default sensor2 and vote metadata kept out of the main deployment path
- `test_data/`: preserved test arrays and metadata
- `scripts/model.py`: MSCNN-BiLSTM model definition
- `scripts/preprocess.py`: raw input loading and training-aligned windowing logic

## Run

```bash
python inference.py --input test_data/test_sensor1_x.npy --output examples/outputs
python examples/run_example.py
```

## Notes

- The packaged default is `sensor1_mscnn_bilstm_binary_best.pth`.
- Voting variants were preserved only as optional artifacts and are not the platform default.
- The original paper and reproduction summaries are preserved in `docs/`.

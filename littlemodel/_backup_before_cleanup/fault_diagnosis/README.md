# NREL Binary Fault Diagnosis Package

## Overview

This folder contains the cleaned binary `healthy vs damaged` NREL fault diagnosis package extracted from the larger reproduction workspace.

The task is a supplemental multisensor binary experiment built on the public NREL gearbox dataset:

- Class 0: `healthy`
- Class 1: `damaged`

This package does not contain the Table 6 proxy four-class main reproduction. It only keeps the binary model artifacts and binary test materials.

## Data Construction

The binary dataset was built from the archived NREL raw files:

- Healthy source files: all `H*.mat`
- Damaged source files: all `D*.mat`

Sensor mapping:

- `sensor1`: train/val use `AN8`, test use `AN9`
- `sensor2`: train/val use `AN5`, test use `AN6`

Preprocessing:

- window size: `4096`
- train/val stride: `4096`
- test stride: `4096`
- per-window z-score normalization
- saved as `float32`

Sample counts:

- train: `400` total (`200` healthy, `200` damaged)
- val: `100` total (`50` healthy, `50` damaged)
- test: `400` total (`200` healthy, `200` damaged)

## Model

Architecture:

- MSCNN-BiLSTM
- multi-scale coarse-grained scales: `[1, 2, 3]`
- parallel 1D CNN branches
- BiLSTM hidden size: `64`
- dropout: `0.5`

Training environment:

- `conda activate pytorch`
- CUDA required
- GPU used: `NVIDIA GeForce RTX 5070 Laptop GPU`

Training settings:

- optimizer: `Adam`
- learning rate: `0.001`
- batch size: `256`
- max epochs: `80`
- early stopping patience: `15`

## Results

Binary test metrics:

| Method | Accuracy | Macro-F1 | Healthy F1 | Damaged F1 |
|---|---:|---:|---:|---:|
| sensor1 | 0.9775 | 0.9775 | 0.9770 | 0.9780 |
| sensor2 | 0.5450 | 0.4262 | 0.6873 | 0.1651 |
| majority_vote | 0.5575 | 0.4498 | 0.6932 | 0.2063 |
| weighted_vote | 0.5575 | 0.4498 | 0.6932 | 0.2063 |

Selected voting weights:

- class `healthy`: `[1, 1]`
- class `damaged`: `[1, 1]`

Interpretation:

- `sensor1` is highly effective for this binary task.
- `sensor2` is much weaker.
- voting does not improve over `sensor1` alone because the weaker sensor drags fusion performance down.

## Folder Contents

`models/`

- `sensor1_mscnn_bilstm_binary_best.pth`
- `sensor2_mscnn_bilstm_binary_best.pth`
- `vote_weights.json`

`results/`

- `metrics.csv`
- `sensor1_confusion_matrix.png`
- `sensor2_confusion_matrix.png`
- `majority_vote_confusion_matrix.png`
- `weighted_vote_confusion_matrix.png`
- `reproduce_summary.md`

`data/`

- `meta.json`
- `test_sensor1_x.npy`
- `test_sensor2_x.npy`
- `test_y.npy`

## Notes

- This package is intended for result checking and lightweight reuse.
- The test arrays are included so the saved models can be re-evaluated directly.
- Train and validation arrays were intentionally not copied here to keep this package smaller and focused on final artifacts.

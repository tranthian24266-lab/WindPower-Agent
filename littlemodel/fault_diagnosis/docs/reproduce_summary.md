# NREL Binary Multisensor Supplement Summary

## Dataset
- Task: binary healthy vs damaged supplement
- Source location: archived raw NREL data moved by the previous cleanup step
- Sensor mapping:
  - sensor1: train/val `AN8`, test `AN9`
  - sensor2: train/val `AN5`, test `AN6`
- Window size: 4096
- Stride: train/val=4096, test=4096
- Class counts: {'train': {'0': 200, '1': 200}, 'val': {'0': 50, '1': 50}, 'test': {'0': 200, '1': 200}}

## Models
- Architecture: MSCNN-BiLSTM
- Device: NVIDIA GeForce RTX 5070 Laptop GPU

## Voting
- Majority vote: confidence tie-break with higher softmax confidence when the two sensors disagree
- Weighted vote: class-specific 2x2 sensor weights searched on validation macro-F1
- Selected weights: {'0': [1, 1], '1': [1, 1]}

## Results
| Method | Accuracy | Macro-F1 | Healthy F1 | Damaged F1 |
|---|---:|---:|---:|---:|
| sensor1 | 0.9775 | 0.9775 | 0.9770 | 0.9780 |
| sensor2 | 0.5450 | 0.4262 | 0.6873 | 0.1651 |
| majority_vote | 0.5575 | 0.4498 | 0.6932 | 0.2063 |
| weighted_vote | 0.5575 | 0.4498 | 0.6932 | 0.2063 |

## Notes
- This is a supplemental experiment added after the main Table 6 proxy four-class reproduction.
- It is methodologically cleaner for multisensor voting because the raw public NREL files clearly distinguish healthy vs damaged gearbox source states.

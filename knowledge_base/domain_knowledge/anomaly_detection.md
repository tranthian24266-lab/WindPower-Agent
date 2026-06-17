# Anomaly Detection Domain Notes

## Task Definition

Anomaly detection measures how far a SCADA sample or window deviates from the learned normal operating pattern.

## Result Interpretation

- The anomaly ratio summarizes how much of the sample looks unusual.
- Higher anomaly counts suggest broader deviation, not a direct fault category label.
- Threshold-based outputs should be compared with recent operating context.

## Risk Meaning

- A rising anomaly ratio can indicate growing instability or distribution shift.
- Persistent anomalies across adjacent windows are stronger evidence than one isolated spike.

## Maintenance Guidance

- Compare anomaly output with alarms, dispatch notes, and maintenance history.
- Investigate operating mode changes before concluding that the model detected a physical fault.

## Applicability Boundary

- This workflow supports abnormality screening, not root-cause classification.
- It is most useful when paired with trend review and follow-up diagnostics.

## Common Misreadings

- Do not interpret anomaly score as a fault label.
- Do not act on a single outlier window without checking surrounding context.

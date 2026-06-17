# RUL Prediction Domain Notes

## Task Definition

Remaining useful life predicts how much usable life is left before the observed degradation reaches the modeled end-of-life pattern.

## Result Interpretation

- `rul_raw` is closest to the native model output and should be treated as the primary signal.
- `rul_clipped` is safer for display and communication but should not replace the raw value in analysis.
- Trends across repeated measurements matter more than one isolated point estimate.

## Risk Meaning

- Low predicted RUL indicates a shorter maintenance window and higher operational urgency.
- Large swings between adjacent runs suggest unstable evidence or changing operating conditions.

## Maintenance Guidance

- Review repeated samples in chronological order before scheduling replacement.
- Combine the prediction with trend charts, vibration context, and operating regime changes.

## Applicability Boundary

- This packaged path reflects a demonstration-oriented run-to-failure reproduction, not a full fleet-level life management system.
- Outputs should be used as decision support, not as a deterministic countdown.

## Common Misreadings

- Do not use clipped RUL as the only engineering value.
- Do not extrapolate a single-sample estimate directly to an entire turbine population.

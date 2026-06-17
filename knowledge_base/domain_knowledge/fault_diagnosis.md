# Fault Diagnosis Domain Notes

## Task Definition

Binary fault diagnosis distinguishes whether the current sample is closer to a healthy state or a damaged state. It does not directly identify a detailed failure mechanism.

## Result Interpretation

- A `healthy` result means the observed features align more closely with the healthy reference distribution.
- A `damaged` result means the sample is more similar to known degraded behavior.
- Confidence near the decision boundary should be treated as weak evidence and reviewed with additional samples.

## Risk Meaning

- High-risk outcomes should trigger additional inspection or secondary evidence review.
- A single positive result is not enough to localize the physical cause of damage.

## Maintenance Guidance

- Re-check the same component with more recent windows if the confidence is unstable.
- Compare the output with inspection notes, alarm history, and maintenance records before closing the case.

## Applicability Boundary

- This workflow is best suited to the healthy-vs-damaged binary task represented by the packaged model.
- It should not be relabeled as a multi-fault classifier without extra evidence.

## Common Misreadings

- Do not interpret `damaged` as a direct maintenance order by itself.
- Do not treat a high confidence score as proof of a specific fault category.

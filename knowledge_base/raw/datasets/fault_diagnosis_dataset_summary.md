# Fault Diagnosis Dataset Summary

- Task type: `fault_diagnosis`
- Dataset name: `NREL/OEDI Wind Turbine Gearbox Condition Monitoring Vibration Analysis Benchmarking Dataset`
- Actual local usage: public wind-turbine vibration subset used for the reproduced fault diagnosis path

## Local usage boundary

- The local reproduction explicitly uses the public NREL/OEDI wind-turbine dataset only.
- The task scope excludes the additional CWRU and XJTU comparison datasets mentioned in the original paper context.
- The packaged platform default narrows the public-dataset branch into a binary `healthy` versus `damaged` classifier.

## Data characteristics relevant to the platform

- Source files are vibration `.mat` files.
- The packaged inference path prefers sensor1-compatible channels and keeps preprocessing aligned with fixed windows and per-window normalization.
- Public-data labels are best interpreted as condition-state evidence for screening rather than complete root-cause annotation.

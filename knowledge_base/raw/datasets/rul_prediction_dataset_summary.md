# RUL Prediction Dataset Summary

- Task type: `rul_prediction`
- Dataset name: `WindTurbineHighSpeedBearingPrognosis`
- Actual local usage: single run-to-failure sequence with 50 `data-*.mat` measurements

## Local usage boundary

- The local reproduction uses one wind turbine high-speed shaft bearing degradation trajectory.
- Each measurement file contains vibration data and may include auxiliary tachometer information.
- The packaged inference path currently depends on the vibration variable used by the local training code.

## Data characteristics relevant to the platform

- The dataset is suitable for paper-style feature trend analysis and demo-scale SVR experiments.
- The single-trajectory setup limits statistical diversity and can make split choice materially affect metrics.
- Reporting and chat answers should frame the current model as a small reproduction baseline rather than a robust life-estimation system.

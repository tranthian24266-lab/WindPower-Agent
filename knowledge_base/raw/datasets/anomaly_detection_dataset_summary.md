# Anomaly Detection Dataset Summary

- Task type: `anomaly_detection`
- Dataset name: `CARE To Compare - Wind Farm A`
- Actual local usage: public SCADA transfer-learning dataset with source turbine 13 and target turbine 10

## Local usage boundary

- The local reproduction uses Wind Farm A from the CARE To Compare public data context.
- The packaged deployment path is centered on transfer from turbine 13 to turbine 10.
- The current anomaly labels are tied to the reproduction pipeline's event and status interpretation rather than a universal fault taxonomy.

## Data characteristics relevant to the platform

- Inputs are SCADA tabular features with a fixed 55-feature order in the packaged model.
- The deployed anomaly detector uses reconstruction RMSE and a learned threshold from the trusted checkpoint metadata.
- Results should be interpreted as operational abnormality evidence that may require follow-up diagnosis.

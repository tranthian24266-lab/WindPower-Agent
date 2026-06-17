# Anomaly Detection Paper Summary

- Task type: `anomaly_detection`
- Model family: `Autoencoder transfer learning`
- Paper title: `Transfer learning applications for autoencoder-based anomaly detection in wind turbines`
- Knowledge role: paper summary for the platform default anomaly detection small model

## Core method

The paper uses an autoencoder to model normal SCADA behavior and studies transfer-learning variants between turbines. The main operational signal is reconstruction-error-based anomaly scoring instead of direct fault classification.

## What was actually reproduced locally

- The local reproduction uses the CARE To Compare public SCADA dataset for Wind Farm A.
- The packaged platform default is the decoder-tuning checkpoint from source turbine 13 to target turbine 10.
- The deployed threshold comes from the current checkpoint metadata and is used to convert anomaly scores into binary anomaly labels.

## Engineering interpretation

- The output is an anomaly score and thresholded anomaly decision, not a direct fault type.
- Transfer-learning quality depends on source-target similarity and split quality.
- The platform should clearly explain that the packaged model is a transfer-learning detector recovered from local reproduction artifacts.

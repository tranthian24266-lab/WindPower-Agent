# Fault Diagnosis Paper Summary

- Task type: `fault_diagnosis`
- Model family: `MSCNN-BiLSTM`
- Paper title: `An intelligent fault diagnosis method for rolling bearings based on multiscale convolutional neural network and bidirectional long short-term memory network`
- Knowledge role: paper summary for the platform default fault diagnosis small model

## Core method

The paper combines multiscale convolution for local pattern extraction with a bidirectional LSTM for temporal dependency modeling. In the windpower project, the reproduced path focuses on the public wind-turbine vibration branch rather than the full set of paper comparison experiments.

## What was actually reproduced locally

- The local reproduction uses the NREL/OEDI public gearbox condition monitoring vibration dataset.
- The packaged platform default is a binary `healthy` versus `damaged` classifier.
- The deployed default is the sensor1 MSCNN-BiLSTM checkpoint because it showed the strongest local test performance.

## Engineering interpretation

- The current packaged model is suitable for binary risk screening, not fine-grained fault-root classification.
- Input preprocessing must stay aligned with training-time windowing and per-window z-score normalization.
- The platform should explain that the default model is a public-dataset supplement around the paper method, not a full reproduction of every benchmark in the paper.

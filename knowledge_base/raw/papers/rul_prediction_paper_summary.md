# RUL Prediction Paper Summary

- Task type: `rul_prediction`
- Model family: `Spectral Kurtosis + SVR`
- Paper title: `Application of spectral kurtosis and support vector regression for high-speed shaft bearing prognostics`
- Knowledge role: paper summary for the platform default RUL small model

## Core method

The paper builds degradation indicators from spectral kurtosis and then predicts remaining useful life with support vector regression. The method emphasizes signal processing and feature engineering instead of deep learning.

## What was actually reproduced locally

- The local reproduction uses one run-to-failure wind turbine high-speed shaft bearing sequence.
- The packaged platform default is a multi-feature SVR demo model that extends the paper-style single-feature path for better demo stability.
- Raw RUL remains the primary model output, while clipped RUL is only a display-safe engineering guard.

## Engineering interpretation

- This small model is a paper-style demo and should not be treated as a fleet-grade life model.
- The single-sequence dataset limits generalization and makes the model sensitive to split choice.
- The platform should keep the distinction between paper-style SK indicators and the extra demo features used by the packaged default.

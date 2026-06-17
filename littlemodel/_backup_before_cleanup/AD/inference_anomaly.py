"""
Inference script for wind turbine anomaly detection.
Loads best_anomaly_model.pt and predicts normal/anomaly.
Usage: python inference_anomaly.py <input.csv> [output.csv]
"""

import os, sys, pickle, torch, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model_ae import create_model, get_batch_size

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def load_model(model_path):
    ckpt = torch.load(model_path, map_location=DEVICE, weights_only=False)
    input_dim = ckpt['input_dim']
    feature_cols = ckpt['feature_cols']
    scaler = ckpt['scaler']
    threshold = ckpt['threshold']

    model = create_model(input_dim)
    model.load_state_dict(ckpt['state_dict'])
    model = model.to(DEVICE)
    model.eval()
    return model, scaler, feature_cols, threshold, ckpt

def predict(model, scaler, feature_cols, threshold, df):
    """Predict anomaly for each row in df."""
    # Extract features
    X_raw = df[feature_cols].values.astype(np.float64)
    # Handle missing values
    X_raw = np.nan_to_num(X_raw, nan=0.0)
    # Scale
    X = scaler.transform(X_raw).astype(np.float32)

    # Compute anomaly scores
    bs = get_batch_size(len(feature_cols))
    all_scores = []
    for i in range(0, len(X), bs):
        batch = torch.tensor(X[i:i+bs]).to(DEVICE)
        with torch.no_grad():
            X_hat = model(batch)
            se = torch.mean((batch - X_hat) ** 2, dim=1)
            rmse = torch.sqrt(se)
            all_scores.append(rmse.cpu().numpy())
    scores = np.concatenate(all_scores)

    # Predict
    pred = (scores >= threshold).astype(int)
    df_out = df.copy()
    df_out['anomaly_score'] = scores
    df_out['prediction'] = pred
    df_out['pred_label'] = df_out['prediction'].map({0: 'normal', 1: 'anomaly'})
    return df_out

def main():
    if len(sys.argv) < 2:
        print("Usage: python inference_anomaly.py <input.csv> [output.csv]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path.replace('.csv', '_predictions.csv')

    model_dir = os.path.dirname(os.path.abspath(__file__))
    model_dir = os.path.join(os.path.dirname(model_dir), "outputs", "final_small_model")
    model_path = os.path.join(model_dir, "best_anomaly_model.pt")

    if not os.path.exists(model_path):
        model_path = os.path.join(os.path.dirname(model_dir), "models", "best_anomaly_model.pt")
    if not os.path.exists(model_path):
        print(f"Model not found at {model_path}")
        print("Looking for any model file...")
        models_dir = os.path.join(os.path.dirname(model_dir), "models")
        for f in sorted(os.listdir(models_dir)):
            if f.endswith('.pt'):
                model_path = os.path.join(models_dir, f)
                print(f"  Using: {model_path}")
                break

    print(f"Loading model: {model_path}")
    model, scaler, feature_cols, threshold, ckpt = load_model(model_path)
    print(f"  Input dim: {ckpt['input_dim']}")
    print(f"  Threshold: {threshold:.6f}")
    print(f"  Features: {len(feature_cols)}")

    # Read input
    df = pd.read_csv(input_path, sep=None, engine='python')
    print(f"Input: {len(df)} rows, {len(df.columns)} columns")

    # Check feature availability
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        print(f"WARNING: {len(missing)} features missing, filling with 0")
        for c in missing:
            df[c] = 0.0

    # Predict
    result = predict(model, scaler, feature_cols, threshold, df)

    # Save
    result.to_csv(output_path, index=False)
    n_anom = result['prediction'].sum()
    print(f"Results: {n_anom}/{len(result)} anomaly predictions ({100*n_anom/len(result):.1f}%)")
    print(f"Saved to: {output_path}")

if __name__ == "__main__":
    main()

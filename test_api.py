import httpx
import time
import json
from pathlib import Path
import traceback

base_url = "http://127.0.0.1:8000/api"
littlemodel_path = Path(r"C:\Users\luzian\Desktop\littlemodel")
client = httpx.Client(trust_env=False, timeout=60.0)

def print_result(name, passed, msg=""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name} {msg}")

def test_health():
    try:
        r = client.get(f"{base_url}/health")
        print_result("Health Check", r.status_code == 200, r.text)
    except Exception as e:
        print_result("Health Check", False, str(e))

def test_models():
    try:
        r = client.get(f"{base_url}/model-catalog/models")
        models = r.json().get("items", [])
        print_result("Model Sync & List", r.status_code == 200 and len(models) >= 3, f"Found {len(models)} models")
    except Exception as e:
        print_result("Model Sync & List", False, str(e))

def upload_file(path_str):
    p = Path(path_str)
    if not p.exists():
        print(f"File not found: {p}")
        return None
    with open(p, "rb") as f:
        files = {"file": (p.name, f, "application/octet-stream")}
        r = client.post(f"{base_url}/upload", files=files)
        if r.status_code == 200:
            return r.json().get("file")
        print(f"Upload failed: {r.status_code} {r.text}")
        return None

def test_upload():
    try:
        f1 = upload_file(littlemodel_path / "fault_diagnosis/test_data/test_sensor1_x.npy")
        f2 = upload_file(littlemodel_path / "anomaly_detection/test_data/test_data_sample.csv")
        f3 = upload_file(littlemodel_path / "rul_prediction/test_data/split_60_40/data-20130406T221209Z.mat")
        print_result("File Upload", f1 and f2 and f3)
        return f1, f2, f3
    except Exception as e:
        print_result("File Upload", False, str(e))
        return None, None, None

def get_id(f):
    return f.get("file_id", f.get("id"))

def test_smart_diag(f1, f2, f3):
    try:
        r1 = client.post(f"{base_url}/diagnose/auto", json={"file_id": get_id(f1)})
        d1 = r1.json()
        
        r2 = client.post(f"{base_url}/diagnose/auto", json={"file_id": get_id(f2)})
        d2 = r2.json()

        r3 = client.post(f"{base_url}/diagnose/auto", json={"file_id": get_id(f3)})
        d3 = r3.json()
        
        c1 = (d1.get("task_type") == "fault_diagnosis")
        c2 = (d2.get("task_type") == "anomaly_detection")
        c3 = (d3.get("task_type") == "rul_prediction")
        
        print_result("Smart Diagnosis Routing NPY -> fault_diagnosis", c1, d1.get("task_type"))
        print_result("Smart Diagnosis Routing CSV -> anomaly_detection", c2, d2.get("task_type"))
        print_result("Smart Diagnosis Routing MAT -> rul_prediction", c3, d3.get("task_type"))
        return d1, d2, d3
    except Exception as e:
        print_result("Smart Diagnosis Routing", False, str(e))
        traceback.print_exc()

def test_batch_diag(f1, f2, f3):
    try:
        r = client.post(f"{base_url}/diagnose/batch", json={"file_ids": [get_id(f1), get_id(f2), get_id(f3)]})
        d = r.json()
        print_result("Batch Diagnosis", r.status_code == 200 and "batch_id" in d, f"Batch response: {d.get('batch_id')}")
    except Exception as e:
        print_result("Batch Diagnosis", False, str(e))

def test_timeline(run_id):
    if not run_id: return
    try:
        r = client.get(f"{base_url}/agent-runs/{run_id}/timeline")
        t = r.json()
        steps = t.get("steps", [])
        print_result("Timeline Data", r.status_code == 200 and len(steps) > 0, f"Steps: {len(steps)}")
    except Exception as e:
        print_result("Timeline Data", False, str(e))

if __name__ == "__main__":
    print("--- Running API Tests ---")
    test_health()
    test_models()
    f1, f2, f3 = test_upload()
    if f1 and f2 and f3:
        d1, d2, d3 = test_smart_diag(f1, f2, f3)
        test_batch_diag(f1, f2, f3)
        if d1 and "run_id" in d1:
            test_timeline(d1["run_id"])
    print("--- Done ---")

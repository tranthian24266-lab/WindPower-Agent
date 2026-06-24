import httpx
import time
import json
import uuid
import os
import shutil
from pathlib import Path
from traceback import print_exc

base_url = "http://127.0.0.1:8000/api"
littlemodel_path = Path(r"C:\Users\luzian\Desktop\littlemodel")
client = httpx.Client(trust_env=False, timeout=60.0)

def print_result(name, passed, msg=""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name} {msg}")

def upload_file(p):
    if not p.exists(): return None
    with open(p, "rb") as f:
        r = client.post(f"{base_url}/upload", files={"file": (p.name, f, "application/octet-stream")})
        if r.status_code == 200: return r.json().get("file")
    return None

def test_mixed_batch():
    p_npy = littlemodel_path / "fault_diagnosis/test_data/test_sensor1_x.npy"
    p_csv = littlemodel_path / "anomaly_detection/test_data/test_data_sample.csv"
    p_bad = Path("bad_mat.mat")
    p_bad.write_text("not a real mat file")
    
    files_data = []
    files_data.append(("files", (p_npy.name, open(p_npy, "rb"), "application/octet-stream")))
    files_data.append(("files", (p_csv.name, open(p_csv, "rb"), "application/octet-stream")))
    files_data.append(("files", (p_bad.name, open(p_bad, "rb"), "application/octet-stream")))
    
    try:
        r = client.post(f"{base_url}/diagnose/batch", files=files_data)
        d = r.json()
        print_result("Mixed Batch (2 valid, 1 bad)", r.status_code == 200 and d.get("total") == 3 and d.get("succeeded") == 2 and d.get("failed") == 1, d)
    except Exception as e:
        print_result("Mixed Batch", False, str(e))
    p_bad.unlink()

def test_empty_batch():
    try:
        r = client.post(f"{base_url}/diagnose/batch", files=[])
        print_result("Empty Batch", r.status_code == 400, r.text)
    except Exception as e:
        print_result("Empty Batch", False, str(e))

def test_over_50_batch():
    try:
        files_data = []
        for i in range(51):
            files_data.append(("files", (f"dummy_{i}.csv", b"dummy", "text/csv")))
        r = client.post(f"{base_url}/diagnose/batch", files=files_data)
        print_result("Over 50 Files Batch", r.status_code == 400, r.text)
    except Exception as e:
        print_result("Over 50 Files Batch", False, str(e))

def test_unsupported_ext():
    try:
        r = client.post(f"{base_url}/upload", files={"file": ("test.exe", b"exe", "application/octet-stream")})
        print_result("Unsupported Ext Upload", r.status_code == 400, r.text)
    except Exception as e:
        print_result("Unsupported Ext Upload", False, str(e))

def test_needs_confirmation():
    p_conf = Path("needs_conf.npy")
    # Empty npy or something that won't match strongly
    import numpy as np
    np.save(p_conf, np.zeros((10, 10)))
    try:
        f = upload_file(p_conf)
        r = client.post(f"{base_url}/diagnose/auto", json={"file_id": f["id"]})
        d = r.json()
        print_result("Needs Confirmation", d.get("status") == "needs_confirmation", d.get("status"))
    except Exception as e:
        print_result("Needs Confirmation", False, str(e))
    finally:
        if p_conf.exists(): p_conf.unlink()

def test_agent_run_persistence():
    p_npy = littlemodel_path / "fault_diagnosis/test_data/test_sensor1_x.npy"
    f = upload_file(p_npy)
    r = client.post(f"{base_url}/diagnose/auto", json={"file_id": f["id"]})
    d = r.json()
    run_id = d.get("run_id")
    case_id = d.get("case_id")
    
    r_timeline = client.get(f"{base_url}/agent-runs/{run_id}/timeline").json()
    steps_count = len(r_timeline.get("timeline", []))
    
    r_run = client.get(f"{base_url}/agent-runs/{run_id}").json()
    run_data = r_run.get("run", {})
    output_case_id = (run_data.get("output_payload") or {}).get("case_id")
    print_result("Run-Case Assoc", case_id == output_case_id and run_data.get("case_id") == case_id, f"Output_case_id={output_case_id}, DB_case_id={run_data.get('case_id')}")
    
    # Save run_id to check after restart
    Path("run_id_to_check.txt").write_text(run_id)

if __name__ == "__main__":
    test_mixed_batch()
    test_empty_batch()
    test_over_50_batch()
    test_unsupported_ext()
    test_needs_confirmation()
    test_agent_run_persistence()

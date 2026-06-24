import httpx
import time
from pathlib import Path

base_url = "http://127.0.0.1:8000/api"
littlemodel_path = Path(r"C:\Users\luzian\Desktop\littlemodel")
client = httpx.Client(trust_env=False, timeout=60.0)

def print_result(name, passed, msg=""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name} {msg}")

def upload_file(p):
    with open(p, "rb") as f:
        r = client.post(f"{base_url}/upload", files={"file": (p.name, f, "application/octet-stream")})
        return r.json().get("file")

def test_agent_run_persistence():
    p_npy = littlemodel_path / "fault_diagnosis/test_data/test_sensor1_x.npy"
    f = upload_file(p_npy)
    r = client.post(f"{base_url}/diagnose/auto", json={"file_id": f["id"]})
    d = r.json()
    run_id = d.get("run_id")
    case_id = d.get("case_id")
    
    # Wait for completion
    time.sleep(2)
    
    r_run = client.get(f"{base_url}/agent-runs/{run_id}").json()
    run_data = r_run.get("run", {})
    output_case_id = (run_data.get("output_payload") or {}).get("case_id")
    db_case_id = run_data.get("case_id")
    
    print_result("Run-Case Assoc", case_id == output_case_id and db_case_id == case_id, f"Output_case_id={output_case_id}, DB_case_id={db_case_id}")
    
    print(f"RUN_ID={run_id}")

test_agent_run_persistence()

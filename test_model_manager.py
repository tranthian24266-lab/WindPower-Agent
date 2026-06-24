import httpx
import json
import zipfile
import io
from pathlib import Path
import time

base_url = "http://127.0.0.1:8000/api"
client = httpx.Client(trust_env=False, timeout=60.0)

def print_result(name, passed, msg=""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name} {msg}")

def upload_model(filename, content):
    files = {"file": (filename, content, "application/zip")}
    return client.post(f"{base_url}/model-catalog/packages/upload", files=files)

def create_zip(files_dict):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for k, v in files_dict.items():
            z.writestr(k, v)
    return buf.getvalue()

def test_non_zip():
    r = client.post(f"{base_url}/model-catalog/packages/upload", files={"file": ("test.npy", b"data", "application/octet-stream")})
    print_result("Non-ZIP Reject", r.status_code == 400, r.text)

def test_missing_card():
    content = create_zip({"predict.py": b"print('hello')"})
    r = upload_model("missing.zip", content)
    print_result("Missing model_card.json Reject", r.status_code == 400, r.text)

def test_invalid_card():
    content = create_zip({"model_card.json": b"{bad_json", "predict.py": b""})
    r = upload_model("invalid.zip", content)
    print_result("Invalid model_card.json Reject", r.status_code == 400, r.text)

def test_missing_entry():
    card = {
        "model_id": "test_model_1",
        "name": "Test Model",
        "task_type": "fault_diagnosis",
        "version": "1.0.0",
        "entry_point": "predict.py"
    }
    content = create_zip({"model_card.json": json.dumps(card).encode()})
    r = upload_model("no_entry.zip", content)
    print_result("Missing entry script Reject", r.status_code == 400, r.text)

def test_valid_model():
    card = {
        "model_id": "test_model_1",
        "name": "Test Model",
        "task_type": "fault_diagnosis",
        "version": "1.0.0",
        "entry_point": "predict.py",
        "author": "tester",
        "supported_input_formats": ["numeric_array"]
    }
    content = create_zip({
        "model_card.json": json.dumps(card).encode(),
        "predict.py": b"def predict(inputs):\n  return {'status': 'ok'}\n"
    })
    r = upload_model("valid.zip", content)
    print_result("Valid Model Upload", r.status_code == 200, r.text)
    upload_id = r.json()["package"]["upload_id"] if r.status_code == 200 else None
    
    # Validate and Publish
    if upload_id:
        r_v = client.post(f"{base_url}/model-catalog/packages/{upload_id}/validate")
        print_result("Validate Model", r_v.status_code == 200, r_v.text)
        r_p = client.post(f"{base_url}/model-catalog/packages/{upload_id}/publish")
        print_result("Publish Model", r_p.status_code == 200, r_p.text)
        if r_p.status_code == 200:
            version_id = r_p.json()["package"]["published_model_version_id"]
        else:
            version_id = None
    else:
        version_id = None

    # Duplicate upload
    r2 = upload_model("valid.zip", content)
    if r2.status_code == 200:
        up_id2 = r2.json()["package"]["upload_id"]
        r_v2 = client.post(f"{base_url}/model-catalog/packages/{up_id2}/validate")
        r_p2 = client.post(f"{base_url}/model-catalog/packages/{up_id2}/publish")
        print_result("Duplicate Model Publish Reject", r_p2.status_code == 400 or r_p2.status_code == 409, r_p2.text)
    
    # Check list
    r_list = client.get(f"{base_url}/model-catalog/models")
    items = r_list.json().get("items", [])
    found = any(m.get("model_id") == "test_model_1" for m in items)
    print_result("Model List Contains New", found, f"Total items: {len(items)}")
    
    # Delete test model
    if version_id:
        r_del = client.delete(f"{base_url}/model-catalog/model-versions/{version_id}")
        print_result("Delete Test Model", r_del.status_code == 200, r_del.text)
    
    # Check DB/List after deletion
    r_list2 = client.get(f"{base_url}/model-catalog/models")
    items2 = r_list2.json().get("items", [])
    found2 = any(m.get("model_id") == "test_model_1" for m in items2)
    print_result("Model List After Deletion", not found2, f"Total items: {len(items2)}")

def test_delete_builtin():
    r = client.delete(f"{base_url}/model-catalog/models/family::scada_ae_decoder_transfer_13_to_10")
    print_result("Delete Built-in Protection", r.status_code == 400 or r.status_code == 403 or r.status_code == 405, r.text)

if __name__ == "__main__":
    test_non_zip()
    test_missing_card()
    test_invalid_card()
    test_missing_entry()
    test_valid_model()
    test_delete_builtin()

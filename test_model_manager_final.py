import httpx
import json
import zipfile
import io

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

def test_valid_model():
    card = {
        "model_id": "test_model_1",
        "name": "Test Model",
        "task_type": "fault_diagnosis",
        "model_version": "1.0.0",
        "adapter_entrypoint": "inference.py:predict",
        "author": "tester",
        "input_contract": {
             "accepted_suffixes": [".csv"],
             "container_types": ["tabular"],
             "required_columns": ["wind_speed"],
             "minimum_required_column_ratio": 0.8
        }
    }
    content = create_zip({
        "model_card.json": json.dumps(card).encode(),
        "inference.py": b"def predict(inputs):\n  return {'status': 'ok'}\n",
        "README.md": b"test model",
        "config.yaml": b"",
        "requirements.txt": b"",
        "weights/model.h5": b"dummy",
        "test_data/test.csv": b"wind_speed\n1.0"
    })
    r = upload_model("valid.zip", content)
    print_result("Valid Model Upload", r.status_code == 200, r.text)
    upload_id = r.json()["package"]["upload_id"] if r.status_code == 200 else None
    
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

    r2 = upload_model("valid.zip", content)
    if r2.status_code == 200:
        up_id2 = r2.json()["package"]["upload_id"]
        r_v2 = client.post(f"{base_url}/model-catalog/packages/{up_id2}/validate")
        r_p2 = client.post(f"{base_url}/model-catalog/packages/{up_id2}/publish")
        print_result("Duplicate Model Publish Reject", r_p2.status_code == 400 or r_p2.status_code == 409, r_p2.text)
    
    r_list = client.get(f"{base_url}/model-catalog/models")
    items = r_list.json().get("items", [])
    found = any(m.get("model_id") == "test_model_1" for m in items)
    print_result("Model List Contains New", found, f"Total items: {len(items)}")
    
    if version_id:
        r_del = client.delete(f"{base_url}/model-catalog/model-versions/{version_id}")
        print_result("Delete Test Model", r_del.status_code == 200, r_del.text)
    
    r_list2 = client.get(f"{base_url}/model-catalog/models")
    items2 = r_list2.json().get("items", [])
    found2 = any(m.get("model_id") == "test_model_1" for m in items2)
    print_result("Model List After Deletion", not found2, f"Total items: {len(items2)}")

if __name__ == "__main__":
    test_valid_model()

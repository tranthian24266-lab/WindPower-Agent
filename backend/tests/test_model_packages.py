from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app


def _model_package_bytes(
    *,
    model_id: str = "demo_fault_model_v1",
    family_code: str = "demo_fault_model",
    version: str = "1.0.0",
) -> bytes:
    model_card = {
        "model_id": model_id,
        "family_code": family_code,
        "model_name": "Demo Fault Model",
        "model_version": version,
        "task_type": "fault_diagnosis",
        "description": "Small deterministic package used by API tests.",
        "framework": "python",
        "runtime_profile": "platform-default",
        "input_format": [".csv"],
        "output_labels": ["healthy"],
        "limitations": ["test only"],
        "input_contract": {
            "accepted_suffixes": [".csv"],
            "container_types": ["tabular"],
            "required_columns": ["value"],
        },
        "adapter_entrypoint": "inference.py:predict",
        "parameter_schema": {
            "threshold": {"type": "number", "default": 0.5, "minimum": 0, "maximum": 1}
        },
    }
    inference = """from __future__ import annotations
from pathlib import Path
import json

def predict(input_path: str, output_dir: str, options: dict | None = None) -> dict:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    result = {
        "status": "success",
        "task_type": "fault_diagnosis",
        "model_id": "demo_fault_model_v1",
        "prediction": {"label": "healthy", "confidence": 1.0},
    }
    (output / "result.json").write_text(json.dumps(result), encoding="utf-8")
    return result
"""
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        prefix = "demo_model/"
        archive.writestr(prefix + "model_card.json", json.dumps(model_card))
        archive.writestr(prefix + "config.yaml", "threshold: 0.5\n")
        archive.writestr(prefix + "inference.py", inference)
        archive.writestr(prefix + "requirements.txt", "# platform default environment\n")
        archive.writestr(prefix + "README.md", "# Demo model\n")
        archive.writestr(prefix + "weights/model.bin", b"test-weight")
        archive.writestr(prefix + "test_data/sample.csv", "value\n1\n")
    return buffer.getvalue()


def _client(tmp_path: Path) -> tuple[TestClient, Settings, Path]:
    littlemodel_root = tmp_path / "littlemodel"
    littlemodel_root.mkdir()
    (littlemodel_root / "model_registry.json").write_text(
        json.dumps({"version": "1.0.0", "models": []}),
        encoding="utf-8",
    )
    backend_root = tmp_path / "backend"
    settings = Settings(
        backend_root=backend_root,
        littlemodel_root=littlemodel_root,
        agent_async_enabled=False,
    )
    return TestClient(create_app(settings)), settings, littlemodel_root


def test_model_package_upload_validate_publish_archive_and_delete(tmp_path: Path) -> None:
    client, settings, littlemodel_root = _client(tmp_path)

    upload = client.post(
        "/api/model-catalog/packages/upload",
        files={"file": ("demo-model.zip", _model_package_bytes(), "application/zip")},
    )
    assert upload.status_code == 200, upload.text
    package = upload.json()["package"]
    upload_id = package["upload_id"]
    assert package["status"] == "inspected"
    assert package["inspection"]["model_card"]["family_code"] == "demo_fault_model"
    assert package["inspection"]["requirements_installation"] == "disabled"

    metadata_update = client.put(
        f"/api/model-catalog/packages/{upload_id}/metadata",
        json={"model_name": "Updated Demo Fault Model", "description": "Updated in the upload wizard."},
    )
    assert metadata_update.status_code == 200
    assert metadata_update.json()["package"]["inspection"]["model_card"]["model_name"] == "Updated Demo Fault Model"

    validation = client.post(f"/api/model-catalog/packages/{upload_id}/validate")
    assert validation.status_code == 200, validation.text
    assert validation.json()["package"]["validation"]["status"] == "passed"
    assert "prediction" in validation.json()["package"]["validation"]["result_keys"]

    publication = client.post(f"/api/model-catalog/packages/{upload_id}/publish")
    assert publication.status_code == 200, publication.text
    published = publication.json()["package"]
    model_version_id = published["published_model_version_id"]
    published_dir = littlemodel_root / published["published_model_dir"]
    assert published_dir.exists()

    detail = client.get(f"/api/model-catalog/model-versions/{model_version_id}")
    assert detail.status_code == 200
    assert detail.json()["model_version"]["status"] == "candidate"
    assert detail.json()["model_version"]["validation_status"] == "passed"
    assert detail.json()["model_version"]["family_code"] == "demo_fault_model"

    archived = client.post(f"/api/model-catalog/model-versions/{model_version_id}/archive")
    assert archived.status_code == 200, archived.text
    assert archived.json()["model_version"]["status"] == "archived"

    deleted = client.delete(f"/api/model-catalog/model-versions/{model_version_id}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["status"] == "deleted"
    assert not published_dir.exists()
    assert Path(deleted.json()["trash_path"]).exists()
    assert client.get(f"/api/model-catalog/model-versions/{model_version_id}").status_code == 404
    assert settings.model_package_staging_path.joinpath(upload_id, "metadata.json").exists()


def test_model_package_rejects_unsafe_zip_paths(tmp_path: Path) -> None:
    client, _, _ = _client(tmp_path)
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("../model_card.json", "{}")

    response = client.post(
        "/api/model-catalog/packages/upload",
        files={"file": ("unsafe.zip", buffer.getvalue(), "application/zip")},
    )

    assert response.status_code == 400
    assert "Unsafe path" in response.json()["detail"]


def test_model_package_supports_multiple_versions_in_one_family(tmp_path: Path) -> None:
    client, _, _ = _client(tmp_path)

    for model_id, version in (("demo_fault_model_v1", "1.0.0"), ("demo_fault_model_v2", "2.0.0")):
        upload = client.post(
            "/api/model-catalog/packages/upload",
            files={"file": (f"{model_id}.zip", _model_package_bytes(model_id=model_id, version=version), "application/zip")},
        )
        assert upload.status_code == 200, upload.text
        upload_id = upload.json()["package"]["upload_id"]
        assert client.post(f"/api/model-catalog/packages/{upload_id}/validate").status_code == 200
        assert client.post(f"/api/model-catalog/packages/{upload_id}/publish").status_code == 200

    family = client.get("/api/model-catalog/models/family::demo_fault_model")
    versions = client.get("/api/model-catalog/models/family::demo_fault_model/versions")
    assert family.status_code == 200
    assert family.json()["model"]["versions_count"] == 2
    assert versions.status_code == 200
    assert {item["version"] for item in versions.json()["versions"]} == {"1.0.0", "2.0.0"}


def test_model_package_rejects_non_admin_when_rbac_is_enabled(tmp_path: Path) -> None:
    client, _, _ = _client(tmp_path)
    client.app.state.settings.rbac_enabled = True

    response = client.post(
        "/api/model-catalog/packages/upload",
        files={"file": ("demo-model.zip", _model_package_bytes(), "application/zip")},
        headers={"X-Actor-Role": "operator"},
    )

    assert response.status_code == 403

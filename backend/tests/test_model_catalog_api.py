from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.model_catalog import ModelCatalogService, ModelFamilyRecord, ModelVersionRecord, to_json_text
from app.core.settings import Settings
from app.main import create_app


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def _create_client(tmp_path: Path) -> TestClient:
    settings = Settings(backend_root=tmp_path, littlemodel_root=LITTLEMODEL_ROOT)
    return TestClient(create_app(settings))


def test_list_model_catalog_models_supports_paging_and_filters(tmp_path: Path) -> None:
    client = _create_client(tmp_path)

    response = client.get(
        "/api/model-catalog/models",
        params={
            "task_type": "fault_diagnosis",
            "status": "production",
            "validation_status": "passed",
            "alias": "default",
            "page": 1,
            "page_size": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["page"] == 1
    assert payload["page_size"] == 1
    assert payload["total"] == 1
    assert payload["has_next"] is False
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["task_type"] == "fault_diagnosis"
    assert item["latest_version"]["status"] == "production"
    assert item["latest_version"]["validation_status"] == "passed"
    assert item["aliases"][0]["alias_name"] == "default"


def test_list_model_catalog_models_supports_search_and_page_size_limit(tmp_path: Path) -> None:
    settings = Settings(
        backend_root=tmp_path,
        littlemodel_root=LITTLEMODEL_ROOT,
        model_catalog_page_size_default=2,
        model_catalog_page_size_max=2,
    )
    client = TestClient(create_app(settings))

    response = client.get(
        "/api/model-catalog/models",
        params={"q": "SCADA", "page": 1, "page_size": 50, "sort_by": "display_name", "sort_order": "desc"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["page_size"] == 2
    assert payload["total"] == 1
    assert payload["items"][0]["family_code"] == "scada_ae_decoder_transfer_13_to_10"


def test_get_model_family_detail_and_versions(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    family_id = "family::nrel_binary_mscnn_bilstm_sensor1"

    detail = client.get(f"/api/model-catalog/models/{family_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()["model"]
    assert detail_payload["family_id"] == family_id
    assert detail_payload["versions_count"] == 1
    assert detail_payload["aliases"][0]["alias_name"] == "default"

    versions = client.get(f"/api/model-catalog/models/{family_id}/versions")
    assert versions.status_code == 200
    versions_payload = versions.json()
    assert versions_payload["count"] == 1
    assert versions_payload["versions"][0]["legacy_model_id"] == "nrel_binary_mscnn_bilstm_sensor1"


def test_get_model_version_detail(tmp_path: Path) -> None:
    client = _create_client(tmp_path)

    response = client.get("/api/model-catalog/model-versions/model_version::hssb_svr_multifeature_60_40")

    assert response.status_code == 200
    payload = response.json()["model_version"]
    assert payload["model_version_id"] == "model_version::hssb_svr_multifeature_60_40"
    assert payload["family_code"] == "hssb_svr_multifeature_60_40"
    assert payload["aliases"][0]["alias_name"] == "default"
    assert payload["feature_names"]


def test_model_catalog_detail_returns_404_for_missing_records(tmp_path: Path) -> None:
    client = _create_client(tmp_path)

    family = client.get("/api/model-catalog/models/family::missing")
    version = client.get("/api/model-catalog/model-versions/model_version::missing")

    assert family.status_code == 404
    assert version.status_code == 404


def test_model_catalog_sync_endpoint_returns_run_summary(tmp_path: Path) -> None:
    client = _create_client(tmp_path)

    response = client.post("/api/model-catalog/sync")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["discovered_count"] == 3
    assert payload["upserted_count"] == 3
    assert payload["sync_run_id"]


def test_model_catalog_validate_endpoint_records_validation_run(tmp_path: Path) -> None:
    client = _create_client(tmp_path)

    response = client.post("/api/model-catalog/model-versions/model_version::scada_ae_decoder_transfer_13_to_10/validate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "passed"
    assert payload["validation_run_id"]
    assert payload["details"]["smoke_input"].endswith(".csv")

    detail = client.get("/api/model-catalog/model-versions/model_version::scada_ae_decoder_transfer_13_to_10")
    assert detail.status_code == 200
    version = detail.json()["model_version"]
    assert version["validation_status"] == "passed"
    assert len(version["validation_runs"]) >= 1


def test_model_catalog_alias_assignment_changes_routing_preview(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    settings = Settings(backend_root=tmp_path, littlemodel_root=LITTLEMODEL_ROOT)
    catalog = ModelCatalogService(settings.database_path)
    timestamp = datetime.now(timezone.utc).isoformat()

    with catalog.database.connect() as connection:
        catalog.upsert_family(
            connection,
            ModelFamilyRecord(
                family_id="family::fault-shadow",
                family_code="fault-shadow",
                display_name="Fault Shadow Model",
                task_type="fault_diagnosis",
                subtask_type=None,
                component="gearbox",
                description="shadow candidate",
                owner="test",
                tags_json=to_json_text(["fault_diagnosis", "shadow"]),
                created_at=timestamp,
                updated_at=timestamp,
            ),
        )
        catalog.upsert_version(
            connection,
            ModelVersionRecord(
                model_version_id="model_version::fault-shadow-v2",
                family_id="family::fault-shadow",
                legacy_model_id="fault-shadow-v2",
                version="2.0.0",
                status="testing",
                validation_status="passed",
                model_dir="fault_diagnosis",
                entrypoint="inference.py:predict",
                framework=None,
                runtime=None,
                dataset="shadow dataset",
                paper_title=None,
                input_format=to_json_text([".npy"]),
                output_schema_json=to_json_text(["healthy", "damaged"]),
                feature_names_json=None,
                limitations_json=to_json_text(["shadow only"]),
                priority=10,
                capabilities_json=to_json_text({"task_type": "fault_diagnosis"}),
                metadata_json=to_json_text({"note": "test candidate"}),
                created_at=timestamp,
                updated_at=timestamp,
                last_validated_at=timestamp,
            ),
        )

    assign = client.put(
        "/api/model-catalog/models/family::fault-shadow/aliases/default",
        json={"model_version_id": "model_version::fault-shadow-v2", "reason": "promote shadow"},
    )
    assert assign.status_code == 200
    assert assign.json()["alias_name"] == "default"

    preview = client.get("/api/model-catalog/routing/preview", params={"task_type": "fault_diagnosis"})
    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["selected_model_version_id"] == "model_version::fault-shadow-v2"
    assert preview_payload["selected_legacy_model_id"] == "fault-shadow-v2"
    assert preview_payload["selection_reason"] == "task_type_default_alias:default"
    assert len(preview_payload["evaluated_candidates"]) >= 2


def test_model_catalog_alias_assignment_rejects_bad_input(tmp_path: Path) -> None:
    client = _create_client(tmp_path)

    bad_alias = client.put(
        "/api/model-catalog/models/family::nrel_binary_mscnn_bilstm_sensor1/aliases/custom",
        json={"model_version_id": "model_version::nrel_binary_mscnn_bilstm_sensor1"},
    )
    bad_family = client.put(
        "/api/model-catalog/models/family::missing/aliases/default",
        json={"model_version_id": "model_version::nrel_binary_mscnn_bilstm_sensor1"},
    )

    assert bad_alias.status_code == 400
    assert bad_family.status_code == 404

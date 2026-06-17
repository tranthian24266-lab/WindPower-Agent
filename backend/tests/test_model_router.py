from __future__ import annotations

from pathlib import Path

from app.core.model_router import ModelRouterService, ModelSelectionRequest
from app.core.model_sync import ModelSyncService


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def test_router_selects_catalog_default_alias_after_sync(tmp_path: Path) -> None:
    database_path = tmp_path / "windpower.db"
    ModelSyncService(database_path, LITTLEMODEL_ROOT).sync_registry()
    router = ModelRouterService(database_path, LITTLEMODEL_ROOT)

    selection = router.select_model(ModelSelectionRequest(task_type="fault_diagnosis"))

    assert selection.legacy_model_id == "nrel_binary_mscnn_bilstm_sensor1"
    assert selection.model_version_id == "model_version::nrel_binary_mscnn_bilstm_sensor1"
    assert selection.model_alias == "default"
    assert selection.selection_reason == "task_type_default_alias:default"


def test_router_falls_back_to_legacy_registry_when_catalog_is_empty(tmp_path: Path) -> None:
    database_path = tmp_path / "windpower.db"
    router = ModelRouterService(database_path, LITTLEMODEL_ROOT)

    selection = router.select_model(ModelSelectionRequest(task_type="rul_prediction"))

    assert selection.legacy_model_id == "hssb_svr_multifeature_60_40"
    assert selection.model_version_id is None
    assert selection.selection_reason == "legacy_registry_active_model"


def test_router_honors_preferred_model_id(tmp_path: Path) -> None:
    database_path = tmp_path / "windpower.db"
    ModelSyncService(database_path, LITTLEMODEL_ROOT).sync_registry()
    router = ModelRouterService(database_path, LITTLEMODEL_ROOT)

    selection = router.select_model(
        ModelSelectionRequest(
            task_type="anomaly_detection",
            preferred_model_id="scada_ae_decoder_transfer_13_to_10",
        )
    )

    assert selection.legacy_model_id == "scada_ae_decoder_transfer_13_to_10"
    assert selection.selection_reason == "preferred_model_id"

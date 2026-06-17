from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3

from app.core.model_catalog import ModelCatalogService
from app.core.model_sync import ModelSyncError, ModelSyncService
from app.db.database import Database, _rewrite_qmark_to_percent_s
from app.db.migration_runner import MigrationRunner


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def test_database_initialize_applies_migrations_and_preserves_legacy_rows(tmp_path: Path) -> None:
    database_path = tmp_path / "windpower.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE diagnosis_cases (
                case_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                model_id TEXT NOT NULL,
                model_name TEXT,
                status TEXT NOT NULL,
                risk_level TEXT,
                result_json_path TEXT NOT NULL,
                output_dir TEXT NOT NULL,
                created_at TEXT NOT NULL,
                report_html_path TEXT,
                report_pdf_path TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO diagnosis_cases (
                case_id,
                file_id,
                task_type,
                model_id,
                model_name,
                status,
                risk_level,
                result_json_path,
                output_dir,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "case-1",
                "file-1",
                "fault_diagnosis",
                "legacy-model",
                "Legacy Model",
                "success",
                "warning",
                "result.json",
                "outputs/case-1",
                "2026-06-04T00:00:00+00:00",
            ),
        )

    database = Database(database_path)
    database.initialize()
    database.initialize()

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        case_row = connection.execute("SELECT case_id FROM diagnosis_cases WHERE case_id = 'case-1'").fetchone()
        migration_rows = connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()

    assert "model_families" in tables
    assert "model_versions" in tables
    assert "model_aliases" in tables
    assert "model_registry_sync_runs" in tables
    assert "knowledge_documents" in tables
    assert "knowledge_chunks" in tables
    assert case_row[0] == "case-1"
    assert [row[0] for row in migration_rows] == [
        "0001_init_schema_migrations",
        "0002_model_catalog",
        "0003_knowledge_rag",
        "0004_enhanced_reports",
        "0005_chat_citations",
        "0006_qdrant_vector_index",
        "0007_case_routing_trace",
        "0008_agent_runtime",
        "0009_agent_run_queue",
        "0010_agent_reviews",
        "0011_tracing_and_eval",
        "0012_multi_agent_governance",
    ]


def test_model_sync_imports_all_registered_models(tmp_path: Path) -> None:
    database_path = tmp_path / "windpower.db"
    service = ModelSyncService(database_path, LITTLEMODEL_ROOT)

    result = service.sync_registry()
    catalog = ModelCatalogService(database_path)

    families = catalog.list_families()
    versions = catalog.list_versions()
    aliases = catalog.list_aliases()
    sync_runs = catalog.list_sync_runs()

    assert result.status == "success"
    assert result.discovered_count == 3
    assert result.upserted_count == 3
    assert len(families) == 3
    assert len(versions) == 3
    assert len(aliases) == 3
    assert sync_runs[-1]["status"] == "success"
    assert {alias["alias_name"] for alias in aliases} == {"default"}
    assert {version["status"] for version in versions} == {"production"}
    assert {version["validation_status"] for version in versions} == {"passed"}


def test_model_sync_rejects_multiple_active_models_for_same_task(tmp_path: Path) -> None:
    littlemodel_root = tmp_path / "littlemodel"
    littlemodel_root.mkdir()
    model_dir = littlemodel_root / "fault_diagnosis"
    model_dir.mkdir()
    (model_dir / "model_card.json").write_text(
        json.dumps({"model_name": "Fault Demo", "model_version": "1.0.0"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (model_dir / "README.md").write_text("fault model", encoding="utf-8")
    (littlemodel_root / "model_registry.json").write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "models": [
                    {
                        "model_id": "fault-a",
                        "task_type": "fault_diagnosis",
                        "model_dir": "fault_diagnosis",
                        "entrypoint": "inference.py:predict",
                        "status": "active",
                    },
                    {
                        "model_id": "fault-b",
                        "task_type": "fault_diagnosis",
                        "model_dir": "fault_diagnosis",
                        "entrypoint": "inference.py:predict",
                        "status": "active",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    service = ModelSyncService(tmp_path / "windpower.db", littlemodel_root)

    try:
        service.sync_registry()
    except ModelSyncError as exc:
        assert "Multiple active models detected" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected ModelSyncError for conflicting active models.")

    catalog = ModelCatalogService(tmp_path / "windpower.db")
    sync_runs = catalog.list_sync_runs()
    assert sync_runs[-1]["status"] == "failed"


def test_database_rewrites_qmark_placeholders_for_postgres() -> None:
    sql = "SELECT * FROM agent_runs WHERE run_id = ? AND status = ?"
    assert _rewrite_qmark_to_percent_s(sql) == "SELECT * FROM agent_runs WHERE run_id = %s AND status = %s"


def test_database_detects_postgres_backend_from_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("WINDPOWER_DATABASE_URL", "postgresql://user:pass@localhost:5432/windpower")
    database = Database(tmp_path / "windpower.db")
    assert database.backend_name == "postgresql"
    monkeypatch.delenv("WINDPOWER_DATABASE_URL", raising=False)


def test_migration_runner_skips_sqlite_pragmas_and_records_version(tmp_path: Path) -> None:
    migrations_path = tmp_path / "migrations"
    migrations_path.mkdir()
    (migrations_path / "0001_test.sql").write_text(
        "PRAGMA foreign_keys=OFF;\nCREATE TABLE IF NOT EXISTS demo (id TEXT PRIMARY KEY);\nPRAGMA foreign_keys=ON;",
        encoding="utf-8",
    )
    database = Database(tmp_path / "runner.db")
    with database.connect() as connection:
        runner = MigrationRunner(migrations_path)
        executed = runner.apply_pending(connection)
        rows = connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()

    assert executed == ["0001_test"]
    assert [row["version"] for row in rows] == ["0001_test"]

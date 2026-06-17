from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.core.report_generator import ReportGeneratorService
from app.core.settings import Settings


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def _create_client(tmp_path: Path) -> TestClient:
    settings = Settings(backend_root=tmp_path, littlemodel_root=LITTLEMODEL_ROOT)
    return TestClient(create_app(settings))


def _create_case(client: TestClient, task_type: str, path: Path) -> str:
    with path.open("rb") as handle:
        upload = client.post("/api/upload", files={"file": (path.name, handle)})
    file_id = upload.json()["file"]["file_id"]
    diagnose = client.post("/api/diagnose", json={"file_id": file_id, "task_type": task_type})
    return diagnose.json()["case_id"]


def test_generate_reports_for_three_task_types(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    cases = [
        _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy"),
        _create_case(
            client,
            "rul_prediction",
            LITTLEMODEL_ROOT / "rul_prediction" / "test_data" / "split_60_40" / "data-20130406T221209Z.mat",
        ),
        _create_case(client, "anomaly_detection", LITTLEMODEL_ROOT / "anomaly_detection" / "test_data" / "test_data_sample.csv"),
    ]

    for case_id in cases:
        generate = client.post(f"/api/reports/{case_id}/generate")
        assert generate.status_code == 200
        payload = generate.json()
        html_path = Path(payload["report_html_path"])
        assert html_path.exists()
        assert payload["download_html_url"] == f"/api/reports/{case_id}/download"
        assert payload["pdf_status"] in {"generated", "dependency_missing", "generation_failed"}
        html = html_path.read_text(encoding="utf-8")
        assert case_id in html
        assert "None" not in html
        assert "undefined" not in html
        assert "NaN" not in html

        detail = client.get(f"/api/reports/{case_id}")
        assert detail.status_code == 200
        assert detail.json()["case_id"] == case_id

        download = client.get(f"/api/reports/{case_id}/download")
        assert download.status_code == 200
        assert "text/html" in download.headers["content-type"]


def test_report_returns_clear_error_for_missing_case(tmp_path: Path) -> None:
    client = _create_client(tmp_path)

    response = client.post("/api/reports/missing-case/generate")

    assert response.status_code == 404
    assert "Diagnosis case does not exist" in response.json()["detail"]


def test_report_detail_returns_404_when_report_not_generated_yet(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    case_id = _create_case(
        client,
        "fault_diagnosis",
        LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy",
    )

    response = client.get(f"/api/reports/{case_id}")

    assert response.status_code == 404
    assert "Report does not exist" in response.json()["detail"]


def test_report_marks_pdf_disabled_when_feature_flag_is_off(tmp_path: Path) -> None:
    settings = Settings(
        backend_root=tmp_path,
        littlemodel_root=LITTLEMODEL_ROOT,
        base_report_pdf_enabled=False,
        _env_file=None,
    )
    client = TestClient(create_app(settings))
    case_id = _create_case(
        client,
        "fault_diagnosis",
        LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy",
    )

    response = client.post(f"/api/reports/{case_id}/generate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pdf_status"] == "disabled"
    assert payload["pdf_reason"] == "base_report_pdf_disabled"
    assert payload["download_pdf_url"] is None
    assert payload["report_status"] == "generated_html_only"


def test_report_pdf_download_returns_file_when_pdf_exists(tmp_path: Path, monkeypatch) -> None:
    def fake_try_generate_pdf(self, html_content: str, pdf_path: Path) -> dict[str, object]:
        pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")
        return {"path": pdf_path, "status": "generated", "reason": None}

    monkeypatch.setattr(ReportGeneratorService, "_try_generate_pdf", fake_try_generate_pdf)

    client = _create_client(tmp_path)
    case_id = _create_case(
        client,
        "fault_diagnosis",
        LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy",
    )

    generate = client.post(f"/api/reports/{case_id}/generate")
    assert generate.status_code == 200
    assert generate.json()["download_pdf_url"] == f"/api/reports/{case_id}/download/pdf"

    download = client.get(f"/api/reports/{case_id}/download/pdf")

    assert download.status_code == 200
    assert "application/pdf" in download.headers["content-type"]


def test_report_pdf_download_returns_404_when_pdf_unavailable(tmp_path: Path) -> None:
    settings = Settings(
        backend_root=tmp_path,
        littlemodel_root=LITTLEMODEL_ROOT,
        base_report_pdf_enabled=False,
        _env_file=None,
    )
    client = TestClient(create_app(settings))
    case_id = _create_case(
        client,
        "fault_diagnosis",
        LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy",
    )
    generate = client.post(f"/api/reports/{case_id}/generate")
    assert generate.status_code == 200

    download = client.get(f"/api/reports/{case_id}/download/pdf")

    assert download.status_code == 404
    assert "PDF report is not available" in download.json()["detail"]

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.core.deepseek_client import DeepSeekChatResult, DeepSeekClientError
from app.core.enhanced_report_llm import EnhancedReportLLMService
from app.core.knowledge_ingestion import KnowledgeIngestionService
from app.core.settings import Settings
from app.main import create_app


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def _create_client(tmp_path: Path, *, enabled: bool = True, **overrides: object) -> TestClient:
    payload: dict[str, object] = {
        "backend_root": tmp_path,
        "littlemodel_root": LITTLEMODEL_ROOT,
        "knowledge_ingestion_enabled": True,
        "knowledge_rag_enabled": True,
        "chat_rag_enabled": True,
        "knowledge_case_ingestion_enabled": True,
        "enhanced_reports_enabled": enabled,
    }
    payload.update(overrides)
    settings = Settings(**payload)
    KnowledgeIngestionService(settings).ingest_default_sources()
    return TestClient(create_app(settings))


def _create_case(client: TestClient, task_type: str, path: Path) -> str:
    with path.open("rb") as handle:
        upload = client.post("/api/upload", files={"file": (path.name, handle)})
    file_id = upload.json()["file"]["file_id"]
    diagnose = client.post("/api/diagnose", json={"file_id": file_id, "task_type": task_type})
    return diagnose.json()["case_id"]


def test_generate_and_fetch_enhanced_report(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    case_id = _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")
    _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    generate = client.post(f"/api/enhanced-reports/{case_id}/generate")

    assert generate.status_code == 200
    payload = generate.json()
    assert payload["report_type"] == "enhanced"
    assert payload["source_mode"] == "enhanced_rule_fallback"
    assert payload["generation_metadata"]["task_template"] == "fault_diagnosis"
    assert payload["generation_metadata"]["pdf"]["status"] in {"generated", "skipped"}
    assert Path(payload["report_json_path"]).exists()
    assert Path(payload["report_html_path"]).exists()
    assert Path(payload["report_docx_path"]).exists()
    if payload["report_pdf_path"] is not None:
        assert Path(payload["report_pdf_path"]).exists()

    detail = client.get(f"/api/enhanced-reports/{case_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    report_json = detail_payload["report_json"]
    assert report_json["case_summary"]["title"] == "案例摘要"
    assert report_json["diagnosis_conclusion"]["title"] == "故障诊断结论"
    assert report_json["citations"]
    assert detail_payload["download_docx_url"]
    if payload["generation_metadata"]["pdf"]["status"] == "generated":
        assert detail_payload["download_pdf_url"]
    else:
        assert detail_payload["download_pdf_url"] is None

    html = client.get(f"/api/enhanced-reports/{case_id}/html")
    assert html.status_code == 200
    assert "故障诊断增强报告" in html.text
    assert "故障诊断概览" in html.text

    docx = client.get(f"/api/enhanced-reports/{case_id}/download/docx")
    assert docx.status_code == 200
    assert docx.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    with ZipFile(Path(payload["report_docx_path"])) as archive:
        assert "word/document.xml" in archive.namelist()
        document_xml = archive.read("word/document.xml").decode("utf-8")
        assert "故障诊断增强报告" in document_xml
        assert "故障证据拆解" in document_xml

    if payload["generation_metadata"]["pdf"]["status"] == "generated":
        pdf = client.get(f"/api/enhanced-reports/{case_id}/download/pdf")
        assert pdf.status_code == 200
        assert pdf.headers["content-type"].startswith("application/pdf")
        assert pdf.content.startswith(b"%PDF")

    versions = client.get(f"/api/enhanced-reports/{case_id}/versions")
    assert versions.status_code == 200
    assert len(versions.json()["versions"]) == 1


def test_enhanced_report_uses_task_specific_templates_for_all_task_types(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    cases = [
        (
            "fault_diagnosis",
            LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy",
            "故障诊断概览",
            "故障诊断增强报告",
        ),
        (
            "rul_prediction",
            LITTLEMODEL_ROOT / "rul_prediction" / "test_data" / "split_60_40" / "data-20130406T221209Z.mat",
            "寿命评估概览",
            "剩余寿命增强报告",
        ),
        (
            "anomaly_detection",
            LITTLEMODEL_ROOT / "anomaly_detection" / "test_data" / "test_data_sample.csv",
            "异常监测概览",
            "异常检测增强报告",
        ),
    ]

    for task_type, sample_path, overview_title, headline in cases:
        case_id = _create_case(client, task_type, sample_path)
        response = client.post(f"/api/enhanced-reports/{case_id}/generate")
        assert response.status_code == 200
        html = client.get(f"/api/enhanced-reports/{case_id}/html")
        assert html.status_code == 200
        assert overview_title in html.text
        assert headline in html.text


def test_enhanced_report_respects_feature_flag(tmp_path: Path) -> None:
    client = _create_client(tmp_path, enabled=False)
    case_id = _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    response = client.post(f"/api/enhanced-reports/{case_id}/generate")

    assert response.status_code == 409
    assert "disabled" in response.json()["detail"]


def test_enhanced_report_can_skip_pdf_when_disabled(tmp_path: Path) -> None:
    client = _create_client(tmp_path, enhanced_report_pdf_enabled=False)
    case_id = _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    response = client.post(f"/api/enhanced-reports/{case_id}/generate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["report_pdf_path"] is None
    assert payload["download_pdf_url"] is None
    assert payload["generation_metadata"]["pdf"]["status"] == "skipped"
    assert payload["generation_metadata"]["pdf"]["reason"] == "feature_flag_disabled"


def test_enhanced_report_can_use_llm_mode(tmp_path: Path, monkeypatch) -> None:
    class FakeDeepSeekClient:
        def __init__(self, settings: Settings):
            self.settings = settings

        def create_chat_completion(
            self,
            *,
            messages: list[dict[str, object]],
            max_tokens: int,
            thinking_enabled: bool,
            reasoning_effort: str,
            response_format: dict[str, object] | None = None,
            temperature: float = 0.1,
        ) -> DeepSeekChatResult:
            assert max_tokens == 1888
            assert thinking_enabled is True
            assert reasoning_effort == "max"
            assert response_format == {"type": "json_object"}
            return DeepSeekChatResult(
                content="""
                {
                  "case_summary": {"title": "LLM 案例摘要", "content": "这是模型生成的案例摘要。", "confidence": 0.91, "evidence_refs": ["case_result"]},
                  "diagnosis_conclusion": {"title": "LLM 诊断结论", "content": "这是模型生成的诊断结论。", "confidence": 0.89, "evidence_refs": ["case_result", "model_metadata"]},
                  "risk_assessment": {"title": "LLM 风险评估", "content": "这是模型生成的风险评估。", "confidence": 0.83, "evidence_refs": ["case_result"]},
                  "evidence_summary": {"title": "LLM 证据摘要", "content": "这是模型生成的证据摘要。", "confidence": 0.8, "evidence_refs": ["case_result"]},
                  "maintenance_actions": {"title": "LLM 维护建议", "content": "这是模型生成的维护建议。", "confidence": 0.79, "evidence_refs": ["case_result"]},
                  "applicability_and_limits": {"title": "LLM 适用边界", "content": "这是模型生成的适用边界。", "confidence": 0.77, "evidence_refs": ["model_metadata"]},
                  "similar_cases": [],
                  "appendix_metrics": [{"label": "Risk Level", "value": "warning"}],
                  "citations": [{"evidence_ref": "case_result", "title": "Case result", "excerpt": "引用摘要", "evidence_type": "case_result", "score": 1.0}]
                }
                """,
                reasoning_content="先汇总证据，再输出 JSON。",
                raw_payload={"usage": {"total_tokens": 64}},
                usage={"total_tokens": 64},
            )

    monkeypatch.setattr("app.core.enhanced_report_llm.DeepSeekClient", FakeDeepSeekClient)

    client = _create_client(
        tmp_path,
        deepseek_api_key="test-key",
        enhanced_report_llm_enabled=True,
        deepseek_max_tokens_report=1888,
        deepseek_reasoning_effort_report="max",
        enhanced_report_json_retry_count=1,
    )
    case_id = _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    response = client.post(f"/api/enhanced-reports/{case_id}/generate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_mode"] == "enhanced_llm"
    assert payload["generation_metadata"]["llm_used"] is True
    assert payload["generation_metadata"]["llm_diagnostics"]["successful_attempt"] == 1
    detail = client.get(f"/api/enhanced-reports/{case_id}")
    assert detail.json()["report_json"]["case_summary"]["title"] == "LLM 案例摘要"


def test_enhanced_report_patches_missing_evidence_refs_in_llm_output(tmp_path: Path, monkeypatch) -> None:
    class FakeDeepSeekClient:
        def __init__(self, settings: Settings):
            self.settings = settings

        def create_chat_completion(
            self,
            *,
            messages: list[dict[str, object]],
            max_tokens: int,
            thinking_enabled: bool,
            reasoning_effort: str,
            response_format: dict[str, object] | None = None,
            temperature: float = 0.1,
        ) -> DeepSeekChatResult:
            return DeepSeekChatResult(
                content="""
                {
                  "case_summary": {"title": "案例摘要", "content": "摘要", "confidence": 0.93, "evidence_refs": []},
                  "diagnosis_conclusion": {"title": "诊断结论", "content": "结论", "confidence": 0.92, "evidence_refs": []},
                  "risk_assessment": {"title": "风险评估", "content": "风险", "confidence": 0.91, "evidence_refs": []},
                  "evidence_summary": {"title": "证据摘要", "content": "证据", "confidence": 0.9, "evidence_refs": []},
                  "maintenance_actions": {"title": "维护建议", "content": "建议", "confidence": 0.89, "evidence_refs": []},
                  "applicability_and_limits": {"title": "适用边界", "content": "限制", "confidence": 0.88, "evidence_refs": []},
                  "similar_cases": [],
                  "appendix_metrics": [],
                  "citations": []
                }
                """,
                reasoning_content=None,
                raw_payload={},
                usage={},
            )

    monkeypatch.setattr("app.core.enhanced_report_llm.DeepSeekClient", FakeDeepSeekClient)

    client = _create_client(
        tmp_path,
        deepseek_api_key="test-key",
        enhanced_report_llm_enabled=True,
    )
    case_id = _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    response = client.post(f"/api/enhanced-reports/{case_id}/generate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_mode"] == "enhanced_llm"
    assert payload["generation_metadata"]["evidence_binding"]["patched_sections"]
    detail = client.get(f"/api/enhanced-reports/{case_id}")
    report_json = detail.json()["report_json"]
    assert report_json["case_summary"]["evidence_refs"] == ["case_result"]
    assert report_json["case_summary"]["confidence"] <= 0.65
    assert report_json["citations"]


def test_enhanced_report_llm_repairs_shape_errors(tmp_path: Path, monkeypatch) -> None:
    class RepairingDeepSeekClient:
        def __init__(self, settings: Settings):
            self.settings = settings
            self.calls = 0

        def create_chat_completion(
            self,
            *,
            messages: list[dict[str, object]],
            max_tokens: int,
            thinking_enabled: bool,
            reasoning_effort: str,
            response_format: dict[str, object] | None = None,
            temperature: float = 0.1,
        ) -> DeepSeekChatResult:
            self.calls += 1
            if self.calls == 1:
                return DeepSeekChatResult(
                    content="""
                    {
                      "case_summary": {"title": "案例摘要", "content": "摘要", "confidence": 0.82, "evidence_refs": ["case_result"]},
                      "diagnosis_conclusion": {"title": "诊断结论", "content": "结论", "confidence": 0.81, "evidence_refs": ["case_result"]},
                      "risk_assessment": {"title": "风险评估", "content": "风险", "confidence": 0.8, "evidence_refs": ["case_result"]},
                      "evidence_summary": {"title": "证据摘要", "content": "证据", "confidence": 0.79, "evidence_refs": ["case_result"]},
                      "maintenance_actions": {"title": "维护建议", "content": "建议", "confidence": 0.78, "evidence_refs": ["case_result"]},
                      "applicability_and_limits": {"title": "限制", "content": "限制", "confidence": 0.77, "evidence_refs": ["model_metadata"]},
                      "similar_cases": {"case_id": "c1", "summary": "single object"},
                      "appendix_metrics": {"Risk Level": "warning"},
                      "citations": {"evidence_ref": "case_result", "title": "Case", "excerpt": "摘录", "evidence_type": "case_result"}
                    }
                    """,
                    reasoning_content=None,
                    raw_payload={},
                    usage={"total_tokens": 42},
                )
            return DeepSeekChatResult(
                content="""
                {
                  "case_summary": {"title": "案例摘要", "content": "摘要", "confidence": 0.82, "evidence_refs": ["case_result"]},
                  "diagnosis_conclusion": {"title": "诊断结论", "content": "结论", "confidence": 0.81, "evidence_refs": ["case_result"]},
                  "risk_assessment": {"title": "风险评估", "content": "风险", "confidence": 0.8, "evidence_refs": ["case_result"]},
                  "evidence_summary": {"title": "证据摘要", "content": "证据", "confidence": 0.79, "evidence_refs": ["case_result"]},
                  "maintenance_actions": {"title": "维护建议", "content": "建议", "confidence": 0.78, "evidence_refs": ["case_result"]},
                  "applicability_and_limits": {"title": "限制", "content": "限制", "confidence": 0.77, "evidence_refs": ["model_metadata"]},
                  "similar_cases": [{"case_id": "c1", "summary": "single object"}],
                  "appendix_metrics": [{"label": "Risk Level", "value": "warning"}],
                  "citations": [{"evidence_ref": "case_result", "title": "Case", "excerpt": "摘录", "evidence_type": "case_result", "score": 1.0}]
                }
                """,
                reasoning_content=None,
                raw_payload={},
                usage={"total_tokens": 40},
            )

    monkeypatch.setattr("app.core.enhanced_report_llm.DeepSeekClient", RepairingDeepSeekClient)

    client = _create_client(
        tmp_path,
        deepseek_api_key="test-key",
        enhanced_report_llm_enabled=True,
        enhanced_report_json_retry_count=1,
    )
    case_id = _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    response = client.post(f"/api/enhanced-reports/{case_id}/generate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_mode"] == "enhanced_llm"
    assert payload["generation_metadata"]["llm_diagnostics"]["repair_used"] is False
    detail = client.get(f"/api/enhanced-reports/{case_id}")
    report_json = detail.json()["report_json"]
    assert report_json["similar_cases"][0]["case_id"] == "c1"
    assert report_json["appendix_metrics"][0]["label"] == "Risk Level"


def test_enhanced_report_llm_retries_after_empty_content(tmp_path: Path, monkeypatch) -> None:
    class RetryingDeepSeekClient:
        def __init__(self, settings: Settings):
            self.settings = settings
            self.calls = 0

        def create_chat_completion(
            self,
            *,
            messages: list[dict[str, object]],
            max_tokens: int,
            thinking_enabled: bool,
            reasoning_effort: str,
            response_format: dict[str, object] | None = None,
            temperature: float = 0.1,
        ) -> DeepSeekChatResult:
            self.calls += 1
            if self.calls == 1:
                raise DeepSeekClientError("DeepSeek API returned empty content.", code="empty_content")
            return DeepSeekChatResult(
                content="""
                {
                  "case_summary": {"title": "案例摘要", "content": "摘要", "confidence": 0.82, "evidence_refs": ["case_result"]},
                  "diagnosis_conclusion": {"title": "诊断结论", "content": "结论", "confidence": 0.81, "evidence_refs": ["case_result"]},
                  "risk_assessment": {"title": "风险评估", "content": "风险", "confidence": 0.8, "evidence_refs": ["case_result"]},
                  "evidence_summary": {"title": "证据摘要", "content": "证据", "confidence": 0.79, "evidence_refs": ["case_result"]},
                  "maintenance_actions": {"title": "维护建议", "content": "建议", "confidence": 0.78, "evidence_refs": ["case_result"]},
                  "applicability_and_limits": {"title": "限制", "content": "限制", "confidence": 0.77, "evidence_refs": ["model_metadata"]},
                  "similar_cases": [],
                  "appendix_metrics": [{"label": "Risk Level", "value": "warning"}],
                  "citations": [{"evidence_ref": "case_result", "title": "Case", "excerpt": "摘录", "evidence_type": "case_result", "score": 1.0}]
                }
                """,
                reasoning_content=None,
                raw_payload={},
                usage={"total_tokens": 32},
            )

    monkeypatch.setattr("app.core.enhanced_report_llm.DeepSeekClient", RetryingDeepSeekClient)

    client = _create_client(
        tmp_path,
        deepseek_api_key="test-key",
        enhanced_report_llm_enabled=True,
        enhanced_report_json_retry_count=1,
    )
    case_id = _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    response = client.post(f"/api/enhanced-reports/{case_id}/generate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_mode"] == "enhanced_llm"
    assert payload["generation_metadata"]["llm_diagnostics"]["repair_used"] is True
    assert payload["generation_metadata"]["llm_diagnostics"]["successful_attempt"] == 2


def test_enhanced_report_llm_can_locally_repair_nearly_valid_json(tmp_path: Path, monkeypatch) -> None:
    class RepairableDeepSeekClient:
        def __init__(self, settings: Settings):
            self.settings = settings

        def create_chat_completion(
            self,
            *,
            messages: list[dict[str, object]],
            max_tokens: int,
            thinking_enabled: bool,
            reasoning_effort: str,
            response_format: dict[str, object] | None = None,
            temperature: float = 0.1,
        ) -> DeepSeekChatResult:
            return DeepSeekChatResult(
                content="""
                {
                  "case_summary": {"title": "案例摘要", "content": "摘要", "confidence": 0.82, "evidence_refs": ["case_result"]},
                  "diagnosis_conclusion": {"title": "诊断结论", "content": "结论", "confidence": 0.81, "evidence_refs": ["case_result"]},
                  "risk_assessment": {"title": "风险评估", "content": "风险", "confidence": 0.8, "evidence_refs": ["case_result"]},
                  "evidence_summary": {"title": "证据摘要", "content": "证据", "confidence": 0.79, "evidence_refs": ["case_result"]},
                  "maintenance_actions": {"title": "维护建议", "content": "建议", "confidence": 0.78, "evidence_refs": ["case_result"]},
                  "applicability_and_limits": {"title": "限制", "content": "限制", "confidence": 0.77, "evidence_refs": ["model_metadata"]},
                  "similar_cases": [],
                  "appendix_metrics": [{"label": "Risk Level", "value": "warning"},],
                  "citations": [{"evidence_ref": "case_result", "title": "Case", "excerpt": "摘录", "evidence_type": "case_result", "score": 1.0},]
                }
                """,
                reasoning_content=None,
                raw_payload={},
                usage={"total_tokens": 18},
            )

    monkeypatch.setattr("app.core.enhanced_report_llm.DeepSeekClient", RepairableDeepSeekClient)

    client = _create_client(
        tmp_path,
        deepseek_api_key="test-key",
        enhanced_report_llm_enabled=True,
        enhanced_report_json_retry_count=1,
    )
    case_id = _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    response = client.post(f"/api/enhanced-reports/{case_id}/generate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_mode"] == "enhanced_llm"
    assert payload["generation_metadata"]["llm_diagnostics"]["repair_used"] is False


def test_enhanced_report_falls_back_when_llm_fails(tmp_path: Path, monkeypatch) -> None:
    class BrokenEnhancedReportLLMService(EnhancedReportLLMService):
        def generate_report_json(
            self,
            *,
            case_id: str,
            evidence: dict[str, object],
        ) -> tuple[dict[str, object], dict[str, object] | None]:
            raise RuntimeError("llm parse failed")

    monkeypatch.setattr("app.core.enhanced_report_service.EnhancedReportLLMService", BrokenEnhancedReportLLMService)

    client = _create_client(
        tmp_path,
        deepseek_api_key="test-key",
        enhanced_report_llm_enabled=True,
    )
    case_id = _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    response = client.post(f"/api/enhanced-reports/{case_id}/generate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_mode"] == "enhanced_rule_fallback"
    assert payload["generation_metadata"]["llm_used"] is False
    assert payload["generation_metadata"]["fallback_reason"] == "llm parse failed"


def test_enhanced_report_can_fetch_specific_version(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    case_id = _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    first = client.post(f"/api/enhanced-reports/{case_id}/generate")
    second = client.post(f"/api/enhanced-reports/{case_id}/generate")

    assert first.status_code == 200
    assert second.status_code == 200
    first_version_id = first.json()["report_version_id"]
    second_version_id = second.json()["report_version_id"]
    assert first_version_id != second_version_id

    detail = client.get(f"/api/enhanced-reports/{case_id}", params={"report_version_id": first_version_id})
    assert detail.status_code == 200
    assert detail.json()["report_version_id"] == first_version_id
    assert f"report_version_id={first_version_id}" in detail.json()["preview_url"]

    html = client.get(f"/api/enhanced-reports/{case_id}/html", params={"report_version_id": second_version_id})
    assert html.status_code == 200
    if second.json()["report_pdf_path"] is not None:
        pdf = client.get(f"/api/enhanced-reports/{case_id}/download/pdf", params={"report_version_id": second_version_id})
        assert pdf.status_code == 200


def test_enhanced_report_does_not_fail_when_pdf_rendering_breaks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.report_template_renderer.ReportTemplateRenderer.render_enhanced_report_pdf",
        lambda self, context, output_path: (_ for _ in ()).throw(RuntimeError("pdf backend failed")),
    )

    client = _create_client(tmp_path)
    case_id = _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    response = client.post(f"/api/enhanced-reports/{case_id}/generate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["report_docx_path"]
    assert payload["report_pdf_path"] is None
    assert payload["generation_metadata"]["pdf"]["status"] == "skipped"
    assert "pdf backend failed" in payload["generation_metadata"]["pdf"]["reason"]

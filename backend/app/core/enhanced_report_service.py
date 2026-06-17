from __future__ import annotations

from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.enhanced_report_llm import EnhancedReportLLMService
from app.core.agent_runtime.guardrails import AgentGuardrails
from app.core.agent_runtime.run_manager import RunManager
from app.core.report_evidence_service import ReportEvidenceService, ReportEvidenceServiceError
from app.core.report_template_renderer import ReportTemplateRenderer
from app.core.settings import Settings
from app.core.telemetry_service import TelemetryService
from app.db.database import Database


class EnhancedReportServiceError(RuntimeError):
    """Raised when an enhanced report cannot be generated or loaded."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class EnhancedReportSection(BaseModel):
    title: str
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(default_factory=list)


class EnhancedReportCitation(BaseModel):
    evidence_ref: str
    title: str
    excerpt: str
    evidence_type: str
    score: Optional[float] = None


class EnhancedSimilarCase(BaseModel):
    case_id: str
    summary: str
    score: Optional[float] = None


class EnhancedReportPayload(BaseModel):
    case_summary: EnhancedReportSection
    diagnosis_conclusion: EnhancedReportSection
    risk_assessment: EnhancedReportSection
    evidence_summary: EnhancedReportSection
    maintenance_actions: EnhancedReportSection
    applicability_and_limits: EnhancedReportSection
    similar_cases: list[EnhancedSimilarCase] = Field(default_factory=list)
    appendix_metrics: list[dict[str, str]] = Field(default_factory=list)
    citations: list[EnhancedReportCitation] = Field(default_factory=list)


class EnhancedReportService:
    SECTION_KEYS = [
        "case_summary",
        "diagnosis_conclusion",
        "risk_assessment",
        "evidence_summary",
        "maintenance_actions",
        "applicability_and_limits",
    ]

    def __init__(self, settings: Settings, llm_service: EnhancedReportLLMService | None = None):
        self.settings = settings
        self.database = Database(settings.database_path)
        self.evidence_service = ReportEvidenceService(settings)
        self.renderer = ReportTemplateRenderer(settings.templates_path)
        self.llm_service = llm_service or EnhancedReportLLMService(settings)
        self.telemetry = TelemetryService(settings)
        self.guardrails = AgentGuardrails()

    def generate(self, case_id: str, *, run_id: str | None = None) -> dict[str, Any]:
        if not self.settings.enhanced_reports_enabled:
            raise EnhancedReportServiceError("Enhanced reports are disabled by feature flag.")

        started = perf_counter()
        try:
            evidence = self.evidence_service.collect(case_id)
        except ReportEvidenceServiceError as exc:
            self._record_generation_summary(
                case_id=case_id,
                task_type=None,
                source_mode="failed",
                generation_metadata={"llm_used": False, "error": str(exc)},
                evidence=None,
                report=None,
                run_id=run_id,
                report_version_id=None,
                duration_ms=self._elapsed_ms(started),
            )
            raise EnhancedReportServiceError(str(exc)) from exc

        try:
            build_report_kwargs: dict[str, Any] = {
                "case_id": case_id,
                "evidence": evidence,
            }
            if "run_id" in inspect.signature(self._build_report).parameters:
                build_report_kwargs["run_id"] = run_id
            report, source_mode, generation_metadata = self._build_report(**build_report_kwargs)
            publication = self.guardrails.assess_report(
                report=report,
                evidence=evidence,
                section_keys=self.SECTION_KEYS,
            )
            generation_metadata = dict(generation_metadata or {})
            generation_metadata["guardrails"] = publication.to_metadata()
            if publication.publication_status == "failed":
                raise EnhancedReportServiceError("Enhanced report guardrail failed: critical sections or evidence bindings are invalid.")
            report_version_id = uuid4().hex
            report_dir = self.settings.reports_path / case_id / "enhanced"
            report_dir.mkdir(parents=True, exist_ok=True)

            report_context = self._build_render_context(case_id, report, evidence)
            json_path = report_dir / f"{report_version_id}.json"
            html_path = report_dir / f"{report_version_id}.html"
            docx_path = report_dir / f"{report_version_id}.docx"
            pdf_path = report_dir / f"{report_version_id}.pdf"

            json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            html_path.write_text(self.renderer.render_enhanced_report(report_context), encoding="utf-8")
            self.renderer.render_enhanced_report_docx(report_context, docx_path)
            pdf_result = self._render_pdf(report_context, pdf_path)

            self._persist_report_version(
                report_version_id=report_version_id,
                case_id=case_id,
                run_id=run_id,
                report=report,
                evidence=evidence,
                json_path=json_path,
                html_path=html_path,
                docx_path=docx_path,
                pdf_path=pdf_result["pdf_path"],
                source_mode=source_mode,
                report_status=publication.publication_status,
            )

            response_generation_metadata = dict(generation_metadata or {})
            response_generation_metadata["pdf"] = {
                "enabled": self.settings.enhanced_report_pdf_enabled,
                "backend": self.settings.enhanced_report_pdf_backend,
                **{key: value for key, value in pdf_result.items() if key != "pdf_path"},
            }

            self._record_generation_summary(
                case_id=case_id,
                task_type=evidence["case_context"]["task_type"],
                source_mode=source_mode,
                generation_metadata=response_generation_metadata,
                evidence=evidence,
                report=report,
                run_id=run_id,
                report_version_id=report_version_id,
                duration_ms=self._elapsed_ms(started),
            )

            return self._build_report_response(
                case_id=case_id,
                report_version_id=report_version_id,
                run_id=run_id,
                source_mode=source_mode,
                report_status=publication.publication_status,
                json_path=json_path,
                html_path=html_path,
                docx_path=docx_path,
                pdf_path=pdf_result["pdf_path"],
                generation_metadata=response_generation_metadata,
            )
        except Exception as exc:
            self._record_generation_summary(
                case_id=case_id,
                task_type=evidence["case_context"]["task_type"],
                source_mode="failed",
                generation_metadata={"llm_used": False, "error": str(exc)},
                evidence=evidence,
                report=None,
                run_id=run_id,
                report_version_id=None,
                duration_ms=self._elapsed_ms(started),
            )
            raise

    def get_latest(self, case_id: str) -> dict[str, Any]:
        row = self._get_latest_report_version(case_id)
        if row is None:
            raise EnhancedReportServiceError(f"Enhanced report does not exist for case_id '{case_id}'.")
        return self._load_report_version(case_id, row)

    def get(self, case_id: str, *, report_version_id: str | None = None) -> dict[str, Any]:
        row = self._get_report_version(case_id, report_version_id=report_version_id)
        if row is None:
            if report_version_id:
                raise EnhancedReportServiceError(
                    f"Enhanced report version '{report_version_id}' does not exist for case_id '{case_id}'."
                )
            raise EnhancedReportServiceError(f"Enhanced report does not exist for case_id '{case_id}'.")
        return self._load_report_version(case_id, row)

    def list_versions(self, case_id: str) -> dict[str, Any]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM report_versions
                WHERE case_id = ? AND report_type = 'enhanced'
                ORDER BY created_at DESC, report_version_id DESC
                """,
                (case_id,),
            ).fetchall()
        return {
            "status": "ok",
            "case_id": case_id,
            "versions": [dict(row) for row in rows],
        }

    def _build_report(
        self,
        *,
        case_id: str,
        evidence: dict[str, Any],
        run_id: str | None = None,
    ) -> tuple[EnhancedReportPayload, str, dict[str, Any] | None]:
        if self.settings.enhanced_report_llm_enabled and self.settings.deepseek_api_key:
            try:
                llm_kwargs = {
                    "case_id": case_id,
                    "evidence": evidence,
                }
                signature = inspect.signature(self.llm_service.generate_report_json)
                if "telemetry_context" in signature.parameters:
                    llm_kwargs["telemetry_context"] = {
                        "case_id": case_id,
                        "run_id": run_id,
                        **self._runtime_trace_context(run_id),
                    }
                report_json, usage = self.llm_service.generate_report_json(**llm_kwargs)
                validated = EnhancedReportPayload.model_validate(report_json)
                normalized, binding_summary = self._ensure_evidence_binding(validated, evidence)
                return (
                    normalized,
                    "enhanced_llm",
                    {
                        "llm_used": True,
                        "usage": (usage or {}).get("usage", {}) if isinstance(usage, dict) else {},
                        "llm_diagnostics": (usage or {}).get("diagnostics", {}) if isinstance(usage, dict) else {},
                        "task_template": evidence["case_context"]["task_type"],
                        "evidence_binding": binding_summary,
                    },
                )
            except Exception as exc:
                fallback_reason, llm_diagnostics = self._extract_fallback_context(exc)
                fallback = self._build_rule_fallback_report(evidence)
                normalized, binding_summary = self._ensure_evidence_binding(fallback, evidence)
                return (
                    normalized,
                    "enhanced_rule_fallback",
                    {
                        "llm_used": False,
                        "fallback_reason": fallback_reason,
                        "llm_diagnostics": llm_diagnostics,
                        "task_template": evidence["case_context"]["task_type"],
                        "evidence_binding": binding_summary,
                    },
                )

        fallback = self._build_rule_fallback_report(evidence)
        normalized, binding_summary = self._ensure_evidence_binding(fallback, evidence)
        return (
            normalized,
            "enhanced_rule_fallback",
            {
                "llm_used": False,
                "task_template": evidence["case_context"]["task_type"],
                "evidence_binding": binding_summary,
            },
        )

    def _build_rule_fallback_report(self, evidence: dict[str, Any]) -> EnhancedReportPayload:
        case_context = evidence["case_context"]
        model_context = evidence["model_context"]
        knowledge_chunks = evidence["retrieved_knowledge"]["chunks"]
        similar_cases = evidence["similar_cases"]
        evidence_items = evidence["evidence_items"]
        evidence_refs = [item["evidence_ref"] for item in evidence_items]
        task_type = case_context["task_type"]

        diagnosis_text = self._build_diagnosis_text(case_context)
        risk_text = self._build_risk_text(case_context, similar_cases)
        maintenance_text = case_context["recommendation"] or self._default_maintenance_text(task_type)
        evidence_text = self._build_evidence_text(knowledge_chunks, similar_cases, task_type)
        limits_text = self._build_limits_text(model_context, task_type)

        return EnhancedReportPayload(
            case_summary=EnhancedReportSection(
                title=self._section_titles(task_type)["case_summary"],
                content=case_context["summary"] or f"该案例属于 {task_type} 任务，已生成增强分析。",
                confidence=0.88,
                evidence_refs=["case_result"],
            ),
            diagnosis_conclusion=EnhancedReportSection(
                title=self._section_titles(task_type)["diagnosis_conclusion"],
                content=diagnosis_text,
                confidence=0.82,
                evidence_refs=["case_result", "model_metadata"],
            ),
            risk_assessment=EnhancedReportSection(
                title=self._section_titles(task_type)["risk_assessment"],
                content=risk_text,
                confidence=0.8,
                evidence_refs=[
                    "case_result",
                    *[item["evidence_ref"] for item in evidence_items if item["evidence_type"] == "similar_case"],
                ],
            ),
            evidence_summary=EnhancedReportSection(
                title=self._section_titles(task_type)["evidence_summary"],
                content=evidence_text,
                confidence=0.78,
                evidence_refs=evidence_refs[:6],
            ),
            maintenance_actions=EnhancedReportSection(
                title=self._section_titles(task_type)["maintenance_actions"],
                content=maintenance_text,
                confidence=0.76,
                evidence_refs=["case_result", "model_metadata"],
            ),
            applicability_and_limits=EnhancedReportSection(
                title=self._section_titles(task_type)["applicability_and_limits"],
                content=limits_text,
                confidence=0.92,
                evidence_refs=["model_metadata"],
            ),
            similar_cases=[
                EnhancedSimilarCase(
                    case_id=item["case_id"],
                    summary=item["summary"] or "相似案例可用于辅助判断。",
                    score=item.get("score"),
                )
                for item in similar_cases
            ],
            appendix_metrics=case_context["metrics"],
            citations=[
                EnhancedReportCitation(
                    evidence_ref=item["evidence_ref"],
                    title=item["title"],
                    excerpt=item["excerpt"],
                    evidence_type=item["evidence_type"],
                    score=item.get("score"),
                )
                for item in evidence_items
            ],
        )

    def _ensure_evidence_binding(
        self,
        report: EnhancedReportPayload,
        evidence: dict[str, Any],
    ) -> tuple[EnhancedReportPayload, dict[str, Any]]:
        fallback_refs = self._default_section_evidence_refs(evidence)
        patched_sections: list[str] = []
        downgraded_sections: list[str] = []

        for section_key in self.SECTION_KEYS:
            section = getattr(report, section_key)
            if section.evidence_refs:
                continue
            section.evidence_refs = list(fallback_refs[section_key])
            patched_sections.append(section_key)
            if section.confidence > 0.65:
                section.confidence = round(min(section.confidence, 0.65), 2)
                downgraded_sections.append(section_key)

        if not report.citations:
            report.citations = [
                EnhancedReportCitation(
                    evidence_ref=item["evidence_ref"],
                    title=item["title"],
                    excerpt=item["excerpt"],
                    evidence_type=item["evidence_type"],
                    score=item.get("score"),
                )
                for item in evidence["evidence_items"][:4]
            ]

        return report, {
            "patched_sections": patched_sections,
            "downgraded_sections": downgraded_sections,
        }

    def _default_section_evidence_refs(self, evidence: dict[str, Any]) -> dict[str, list[str]]:
        knowledge_refs = [
            item["evidence_ref"]
            for item in evidence["evidence_items"]
            if item["evidence_type"] == "knowledge_chunk"
        ]
        similar_case_refs = [
            item["evidence_ref"]
            for item in evidence["evidence_items"]
            if item["evidence_type"] == "similar_case"
        ]
        return {
            "case_summary": ["case_result"],
            "diagnosis_conclusion": ["case_result", "model_metadata"],
            "risk_assessment": ["case_result", *(similar_case_refs[:2] or knowledge_refs[:1])],
            "evidence_summary": knowledge_refs[:4] or ["model_metadata"],
            "maintenance_actions": ["case_result", "model_metadata"],
            "applicability_and_limits": ["model_metadata", *(knowledge_refs[:1])],
        }

    def _section_titles(self, task_type: str) -> dict[str, str]:
        if task_type == "fault_diagnosis":
            return {
                "case_summary": "案例摘要",
                "diagnosis_conclusion": "故障诊断结论",
                "risk_assessment": "故障风险评估",
                "evidence_summary": "诊断证据摘要",
                "maintenance_actions": "检修与复核建议",
                "applicability_and_limits": "适用边界与限制",
            }
        if task_type == "rul_prediction":
            return {
                "case_summary": "案例摘要",
                "diagnosis_conclusion": "寿命评估结论",
                "risk_assessment": "剩余寿命风险评估",
                "evidence_summary": "寿命证据摘要",
                "maintenance_actions": "维护窗口建议",
                "applicability_and_limits": "适用边界与限制",
            }
        return {
            "case_summary": "案例摘要",
            "diagnosis_conclusion": "异常检测结论",
            "risk_assessment": "运行风险评估",
            "evidence_summary": "异常证据摘要",
            "maintenance_actions": "监测与复核建议",
            "applicability_and_limits": "适用边界与限制",
        }

    def _build_diagnosis_text(self, case_context: dict[str, Any]) -> str:
        result = case_context["result"]
        if case_context["task_type"] == "fault_diagnosis":
            return (
                f"模型给出的预测结果为 {result.get('prediction')}，"
                f"置信度为 {result.get('confidence')}，风险等级为 {result.get('risk_level')}。"
            )
        if case_context["task_type"] == "rul_prediction":
            return (
                f"模型输出的原始 RUL 为 {result.get('rul_raw')}，"
                f"展示保护后的 RUL 为 {result.get('rul_clipped')}，风险等级为 {result.get('risk_level')}。"
            )
        return (
            f"异常比例为 {result.get('anomaly_ratio')}，异常样本数为 {result.get('num_anomalies')}，"
            f"风险等级为 {result.get('risk_level')}。"
        )

    def _build_risk_text(self, case_context: dict[str, Any], similar_cases: list[dict[str, Any]]) -> str:
        text = f"当前案例风险等级为 {case_context.get('risk_level') or 'unknown'}。"
        if similar_cases:
            text += f" 系统同时找到 {len(similar_cases)} 个同任务历史案例，可用于横向比较。"
        return text

    def _build_evidence_text(
        self,
        knowledge_chunks: list[dict[str, Any]],
        similar_cases: list[dict[str, Any]],
        task_type: str,
    ) -> str:
        parts: list[str] = []
        if knowledge_chunks:
            parts.append(f"知识库检索到 {len(knowledge_chunks)} 个相关片段。")
        if similar_cases:
            parts.append(f"历史相似案例数量为 {len(similar_cases)}。")
        if not parts:
            prefix = {
                "fault_diagnosis": "当前增强报告主要基于诊断结果与模型元数据生成。",
                "rul_prediction": "当前增强报告主要基于寿命结果与模型元数据生成。",
                "anomaly_detection": "当前增强报告主要基于异常结果与模型元数据生成。",
            }
            return prefix.get(task_type, "当前增强报告主要基于案例结果与模型元数据生成。")
        return " ".join(parts)

    def _build_limits_text(self, model_context: dict[str, Any], task_type: str) -> str:
        limitations = model_context.get("limitations") or []
        if limitations:
            return "；".join(str(item) for item in limitations[:3])
        defaults = {
            "fault_diagnosis": "当前模型适合做样本级故障状态识别，不应单独视为根因定位结论。",
            "rul_prediction": "当前模型适合做寿命趋势辅助判断，仍需结合检修策略与现场工况解释。",
            "anomaly_detection": "当前模型适合做异常筛查与告警辅助，迁移学习效果受源目标机组相似度影响。",
        }
        return defaults.get(task_type, "当前模型的适用边界以本地模型卡和复现实验说明为准。")

    def _default_maintenance_text(self, task_type: str) -> str:
        defaults = {
            "fault_diagnosis": "建议结合现场复核、部件巡检与趋势监测进一步确认故障处置方案。",
            "rul_prediction": "建议结合趋势监测和检修窗口安排，确定维护优先级与复测节奏。",
            "anomaly_detection": "建议结合机组工况、告警上下文和人工复核，确认异常是否需要升级处理。",
        }
        return defaults.get(task_type, "建议结合现场复核与趋势监测进一步确认。")

    def _build_render_context(
        self,
        case_id: str,
        report: EnhancedReportPayload,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "case_id": case_id,
            "report": report.model_dump(),
            "case_context": evidence["case_context"],
            "model_context": evidence["model_context"],
            "retrieved_knowledge": evidence["retrieved_knowledge"],
            "similar_cases": evidence["similar_cases"],
        }

    def _render_pdf(self, report_context: dict[str, Any], pdf_path: Path) -> dict[str, Any]:
        if not self.settings.enhanced_report_pdf_enabled:
            return {
                "status": "skipped",
                "reason": "feature_flag_disabled",
                "pdf_path": None,
            }
        if self.settings.enhanced_report_pdf_backend == "disabled":
            return {
                "status": "skipped",
                "reason": "backend_disabled",
                "pdf_path": None,
            }
        try:
            generated = self.renderer.render_enhanced_report_pdf(report_context, pdf_path)
            return {
                "status": "generated",
                "pdf_path": generated,
            }
        except Exception as exc:
            return {
                "status": "skipped",
                "reason": str(exc),
                "pdf_path": None,
            }

    def _persist_report_version(
        self,
        *,
        report_version_id: str,
        case_id: str,
        run_id: str | None,
        report: EnhancedReportPayload,
        evidence: dict[str, Any],
        json_path: Path,
        html_path: Path,
        docx_path: Path,
        pdf_path: Path | None,
        source_mode: str,
        report_status: str,
    ) -> None:
        now = _utcnow()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO report_versions (
                    report_version_id,
                    case_id,
                    run_id,
                    report_type,
                    status,
                    source_mode,
                    report_json_path,
                    report_html_path,
                    report_docx_path,
                    report_pdf_path,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_version_id,
                    case_id,
                    run_id,
                    "enhanced",
                    report_status,
                    source_mode,
                    str(json_path),
                    str(html_path),
                    str(docx_path),
                    str(pdf_path) if pdf_path else None,
                    now,
                    now,
                ),
            )
            for citation in report.citations:
                matching = next(
                    (item for item in evidence["evidence_items"] if item["evidence_ref"] == citation.evidence_ref),
                    None,
                )
                connection.execute(
                    """
                    INSERT INTO report_evidence_items (
                        evidence_item_id,
                        report_version_id,
                        evidence_type,
                        source_id,
                        title,
                        excerpt,
                        score,
                        metadata_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid4().hex,
                        report_version_id,
                        citation.evidence_type,
                        matching["source_id"] if matching else None,
                        citation.title,
                        citation.excerpt,
                        citation.score,
                        json.dumps(matching["metadata"], ensure_ascii=False)
                        if matching
                        else json.dumps({}, ensure_ascii=False),
                        now,
                    ),
                )

    def _get_latest_report_version(self, case_id: str) -> dict[str, Any] | None:
        return self._get_report_version(case_id, report_version_id=None)

    def _get_report_version(self, case_id: str, report_version_id: str | None) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            if report_version_id:
                row = connection.execute(
                    """
                    SELECT *
                    FROM report_versions
                    WHERE case_id = ? AND report_type = 'enhanced' AND report_version_id = ?
                    LIMIT 1
                    """,
                    (case_id, report_version_id),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT *
                    FROM report_versions
                    WHERE case_id = ? AND report_type = 'enhanced'
                    ORDER BY created_at DESC, report_version_id DESC
                    LIMIT 1
                    """,
                    (case_id,),
                ).fetchone()
        return dict(row) if row is not None else None

    def _load_report_version(self, case_id: str, row: dict[str, Any]) -> dict[str, Any]:
        json_path = Path(row["report_json_path"])
        html_path = Path(row["report_html_path"]) if row.get("report_html_path") else None
        docx_path = Path(row["report_docx_path"]) if row.get("report_docx_path") else None
        pdf_path = Path(row["report_pdf_path"]) if row.get("report_pdf_path") else None
        if not json_path.exists():
            raise EnhancedReportServiceError(
                f"Enhanced report JSON file does not exist for case_id '{case_id}': {json_path}"
            )
        if html_path is not None and not html_path.exists():
            raise EnhancedReportServiceError(
                f"Enhanced report HTML file does not exist for case_id '{case_id}': {html_path}"
            )
        if docx_path is not None and not docx_path.exists():
            raise EnhancedReportServiceError(
                f"Enhanced report DOCX file does not exist for case_id '{case_id}': {docx_path}"
            )
        if pdf_path is not None and not pdf_path.exists():
            pdf_path = None

        report_json = json.loads(json_path.read_text(encoding="utf-8"))
        report_version_id = str(row["report_version_id"])
        query_suffix = f"?report_version_id={report_version_id}"
        return {
            "status": "ok",
            "case_id": case_id,
            "report_version_id": report_version_id,
            "run_id": str(row["run_id"]) if row.get("run_id") else None,
            "report_type": row["report_type"],
            "report_status": row["status"],
            "source_mode": row["source_mode"],
            "report_json_path": str(json_path),
            "report_html_path": str(html_path) if html_path else None,
            "report_docx_path": str(docx_path) if docx_path else None,
            "report_pdf_path": str(pdf_path) if pdf_path else None,
            "report_json": report_json,
            "html_content": html_path.read_text(encoding="utf-8") if html_path else None,
            "preview_url": f"/api/enhanced-reports/{case_id}/html{query_suffix}",
            "download_docx_url": f"/api/enhanced-reports/{case_id}/download/docx{query_suffix}" if docx_path else None,
            "download_pdf_url": f"/api/enhanced-reports/{case_id}/download/pdf{query_suffix}" if pdf_path else None,
            "versions_url": f"/api/enhanced-reports/{case_id}/versions",
        }

    def _build_report_response(
        self,
        *,
        case_id: str,
        report_version_id: str,
        run_id: str | None,
        source_mode: str,
        report_status: str,
        json_path: Path,
        html_path: Path,
        docx_path: Path,
        pdf_path: Path | None,
        generation_metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "status": "ok",
            "case_id": case_id,
            "report_version_id": report_version_id,
            "run_id": run_id,
            "report_type": "enhanced",
            "report_status": report_status,
            "source_mode": source_mode,
            "report_json_path": str(json_path),
            "report_html_path": str(html_path),
            "report_docx_path": str(docx_path),
            "report_pdf_path": str(pdf_path) if pdf_path else None,
            "preview_url": f"/api/enhanced-reports/{case_id}/html",
            "download_docx_url": f"/api/enhanced-reports/{case_id}/download/docx",
            "download_pdf_url": f"/api/enhanced-reports/{case_id}/download/pdf" if pdf_path else None,
            "versions_url": f"/api/enhanced-reports/{case_id}/versions",
            "generation_metadata": generation_metadata or {},
        }

    def _record_generation_summary(
        self,
        *,
        case_id: str,
        task_type: str | None,
        source_mode: str,
        generation_metadata: dict[str, Any],
        evidence: dict[str, Any] | None,
        report: EnhancedReportPayload | None,
        run_id: str | None,
        report_version_id: str | None,
        duration_ms: int,
    ) -> None:
        self.telemetry.record(
            "enhanced_report_generation",
            {
                "case_id": case_id,
                "task_type": task_type,
                "run_id": run_id,
                "report_version_id": report_version_id,
                **self._runtime_trace_context(run_id),
                "source_mode": source_mode,
                "report_status": (generation_metadata.get("guardrails") or {}).get("publication_status"),
                "llm_used": bool(generation_metadata.get("llm_used")),
                "fallback_reason": generation_metadata.get("fallback_reason"),
                "task_template": generation_metadata.get("task_template"),
                "llm_attempt_count": ((generation_metadata.get("llm_diagnostics") or {}).get("attempt_count")),
                "llm_failure_category": ((generation_metadata.get("llm_diagnostics") or {}).get("final_failure_category")),
                "llm_repair_used": bool((generation_metadata.get("llm_diagnostics") or {}).get("repair_used")),
                "chunk_count": len(evidence["retrieved_knowledge"]["chunks"]) if evidence else 0,
                "citation_count": len(report.citations) if report else 0,
                "similar_case_count": len(evidence["similar_cases"]) if evidence else 0,
                "pdf_status": (generation_metadata.get("pdf") or {}).get("status"),
                "usage": generation_metadata.get("usage") or {},
                "duration_ms": duration_ms,
            },
        )

    def _extract_fallback_context(self, exc: Exception) -> tuple[str, dict[str, Any]]:
        message = str(exc)
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return message, {}
        if not isinstance(payload, dict):
            return message, {}
        fallback_reason = str(payload.get("message") or message)
        diagnostics = payload.get("diagnostics")
        return fallback_reason, diagnostics if isinstance(diagnostics, dict) else {}

    def _elapsed_ms(self, started: float) -> int:
        return int((perf_counter() - started) * 1000)

    def _runtime_trace_context(self, run_id: str | None) -> dict[str, Any]:
        if not run_id:
            return {}
        detail = RunManager(self.settings.database_path).get_run_detail(run_id)
        if not detail:
            return {}
        trace_id = detail.get("trace_id")
        return {"trace_id": trace_id} if trace_id else {}

from __future__ import annotations

import json
from math import isnan
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.case_store import CaseStoreError, CaseStoreService
from app.core.model_registry import ModelRegistryError, ModelRegistryService
from app.core.settings import Settings


class ReportGenerationError(RuntimeError):
    """Raised when a report cannot be generated or loaded."""


class ReportGeneratorService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.case_store = CaseStoreService(settings.database_path)
        self.registry = ModelRegistryService(settings.resolved_littlemodel_root)
        self.environment = Environment(
            loader=FileSystemLoader(settings.templates_path),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def generate(self, case_id: str) -> dict[str, Any]:
        case = self._load_case(case_id)
        model_meta = self._get_model_meta(case["model_id"])
        context = self._build_context(case, model_meta)

        report_dir = self.settings.reports_path / case_id
        report_dir.mkdir(parents=True, exist_ok=True)
        html_path = report_dir / "report.html"
        metadata_path = report_dir / "report_metadata.json"
        html_content = self.environment.get_template("report_template.html").render(**context)
        html_path.write_text(html_content, encoding="utf-8")

        pdf_result = self._try_generate_pdf(context, report_dir / "report.pdf")
        pdf_path = pdf_result["path"]
        metadata = self._build_generation_metadata(pdf_result)
        self._write_metadata(metadata_path, metadata)
        self.case_store.update_report_paths(case_id, str(html_path), str(pdf_path) if pdf_path else None)
        return self._build_report_payload(case_id, html_path, pdf_path, metadata)

    def get_report(self, case_id: str) -> dict[str, Any]:
        case = self._load_case(case_id)
        report_html_path = case.get("report_html_path")
        if not report_html_path:
            raise ReportGenerationError(f"Report does not exist for case_id '{case_id}'.")

        html_path = Path(report_html_path)
        if not html_path.exists():
            raise ReportGenerationError(f"Report HTML file does not exist for case_id '{case_id}': {html_path}")

        pdf_path = Path(case["report_pdf_path"]) if case.get("report_pdf_path") else None
        if pdf_path is not None and not pdf_path.exists():
            pdf_path = None

        metadata = self._load_metadata(html_path.parent / "report_metadata.json")
        if metadata is None:
            metadata = self._build_generation_metadata(
                self._build_pdf_result(
                    pdf_path,
                    status="generated" if pdf_path is not None else "not_generated",
                    reason=None if pdf_path is not None else "pdf_not_generated_for_existing_report",
                )
            )

        return self._build_report_payload(
            case_id,
            html_path,
            pdf_path,
            metadata,
            html_content=html_path.read_text(encoding="utf-8"),
        )

    def _build_report_payload(
        self,
        case_id: str,
        html_path: Path,
        pdf_path: Path | None,
        metadata: dict[str, Any],
        *,
        html_content: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "status": "ok",
            "case_id": case_id,
            "report_html_path": str(html_path),
            "report_pdf_path": str(pdf_path) if pdf_path else None,
            "preview_url": f"/api/reports/{case_id}/html",
            "download_url": f"/api/reports/{case_id}/download",
            "download_html_url": f"/api/reports/{case_id}/download",
            "download_pdf_url": f"/api/reports/{case_id}/download/pdf" if pdf_path else None,
            "report_status": metadata.get("report_status", "generated"),
            "pdf_status": metadata.get("pdf_status", "not_generated"),
            "pdf_reason": metadata.get("pdf_reason"),
            "generation_metadata": metadata,
        }
        if html_content is not None:
            payload["html_content"] = html_content
        return payload

    def _load_case(self, case_id: str) -> dict[str, Any]:
        try:
            return self.case_store.get_case_detail(case_id)
        except CaseStoreError as exc:
            raise ReportGenerationError(str(exc)) from exc

    def _get_model_meta(self, model_id: str) -> dict[str, Any]:
        try:
            models = self.registry.list_models()
        except ModelRegistryError as exc:
            raise ReportGenerationError(str(exc)) from exc
        for model in models:
            if model["model_id"] == model_id:
                return model
        return {}

    def _build_context(self, case: dict[str, Any], model_meta: dict[str, Any]) -> dict[str, Any]:
        result = case["result"]
        metrics = self._build_metrics(case["task_type"], result)
        return {
            "case_id": case["case_id"],
            "task_type": case["task_type"],
            "model_id": case["model_id"],
            "model_name": case.get("model_name") or model_meta.get("model_name") or case["model_id"],
            "created_at": case["created_at"],
            "original_filename": case.get("original_filename") or "",
            "stored_path": case.get("stored_path") or "",
            "risk_level": case.get("risk_level") or result.get("risk_level") or "unknown",
            "summary": result.get("summary") or "",
            "recommendation": result.get("recommendation") or "",
            "paper_title": model_meta.get("paper_title") or "",
            "dataset": model_meta.get("dataset") or "",
            "readme_summary": model_meta.get("readme_summary") or "",
            "limitations": model_meta.get("limitations") or [],
            "metrics": metrics,
            "result_json": json.dumps(self._json_safe(result), ensure_ascii=False, indent=2),
        }

    def _build_metrics(self, task_type: str, result: dict[str, Any]) -> list[dict[str, str]]:
        if task_type == "fault_diagnosis":
            return [
                {"label": "预测结果", "value": str(result.get("prediction", ""))},
                {"label": "置信度", "value": self._format_value(result.get("confidence"))},
                {"label": "风险等级", "value": str(result.get("risk_level", ""))},
                {"label": "类别概率", "value": self._format_value(result.get("class_probabilities"))},
            ]
        if task_type == "rul_prediction":
            return [
                {"label": "原始 RUL", "value": self._format_value(result.get("rul_raw"))},
                {"label": "展示 RUL", "value": self._format_value(result.get("rul_clipped"))},
                {"label": "RUL 单位", "value": str(result.get("rul_unit", ""))},
                {"label": "风险等级", "value": str(result.get("risk_level", ""))},
                {"label": "特征", "value": self._format_value(result.get("features"))},
            ]
        if task_type == "anomaly_detection":
            return [
                {"label": "阈值", "value": self._format_value(result.get("threshold"))},
                {"label": "样本数", "value": self._format_value(result.get("num_samples"))},
                {"label": "异常样本数", "value": self._format_value(result.get("num_anomalies"))},
                {"label": "异常比例", "value": self._format_value(result.get("anomaly_ratio"))},
                {"label": "平均分数", "value": self._format_value(result.get("mean_anomaly_score"))},
                {"label": "最大分数", "value": self._format_value(result.get("max_anomaly_score"))},
                {"label": "风险等级", "value": str(result.get("risk_level", ""))},
            ]
        return [{"label": key, "value": self._format_value(value)} for key, value in result.items()]

    def _format_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float) and isnan(value):
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(self._json_safe(value), ensure_ascii=False)
        return str(value)

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        if isinstance(value, float) and isnan(value):
            return None
        return value

    def _try_generate_pdf(self, context: dict[str, Any], pdf_path: Path) -> dict[str, Any]:
        if not self.settings.base_report_pdf_enabled:
            return self._build_pdf_result(None, status="disabled", reason="base_report_pdf_disabled")

        try:
            self._render_pdf(context, pdf_path)
        except Exception as exc:
            return self._build_pdf_result(None, status="generation_failed", reason=f"reportlab_failed:{exc}")
        return self._build_pdf_result(pdf_path, status="generated", reason=None)

    def _render_pdf(self, context: dict[str, Any], pdf_path: Path) -> None:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            from reportlab.pdfbase.pdfmetrics import registerFont
            from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle
        except Exception as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(f"PDF backend 'reportlab' is unavailable: {exc}") from exc

        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        registerFont(UnicodeCIDFont("STSong-Light"))

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "BaseReportTitle",
            parent=styles["Title"],
            fontName="STSong-Light",
            fontSize=20,
            leading=26,
            textColor=colors.HexColor("#173020"),
        )
        heading_style = ParagraphStyle(
            "BaseReportHeading",
            parent=styles["Heading2"],
            fontName="STSong-Light",
            fontSize=13,
            leading=18,
            textColor=colors.HexColor("#173020"),
            spaceBefore=8,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "BaseReportBody",
            parent=styles["BodyText"],
            fontName="STSong-Light",
            fontSize=10.5,
            leading=16,
            textColor=colors.HexColor("#415244"),
        )
        code_style = ParagraphStyle(
            "BaseReportCode",
            parent=body_style,
            fontName="STSong-Light",
            fontSize=8.5,
            leading=12,
        )

        story: list[Any] = [
            Paragraph(f"{context['case_id']} 基础报告", title_style),
            Spacer(1, 4 * mm),
            Paragraph(f"任务类型：{context['task_type']}", body_style),
            Paragraph(f"模型：{context['model_name']}", body_style),
            Paragraph(f"风险等级：{context['risk_level']}", body_style),
            Paragraph(f"创建时间：{context['created_at']}", body_style),
            Spacer(1, 4 * mm),
        ]

        if context["summary"]:
            story.extend(
                [
                    Paragraph("结果摘要", heading_style),
                    Paragraph(str(context["summary"]), body_style),
                ]
            )
        if context["recommendation"]:
            story.extend(
                [
                    Paragraph("维护建议", heading_style),
                    Paragraph(str(context["recommendation"]), body_style),
                ]
            )

        story.append(Paragraph("关键指标", heading_style))
        metric_rows = [[item["label"], item["value"]] for item in context["metrics"]]
        metric_table = Table(metric_rows, colWidths=[42 * mm, 128 * mm])
        metric_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6FAF6")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7E1D8")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.extend([metric_table, Spacer(1, 4 * mm)])

        if context["limitations"]:
            story.append(Paragraph("适用边界", heading_style))
            for item in context["limitations"]:
                story.append(Paragraph(f"- {item}", body_style))

        story.append(Paragraph("原始结果 JSON", heading_style))
        story.append(Preformatted(context["result_json"], code_style))

        document = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title=f"{context['case_id']} 基础报告",
        )
        document.build(story)

    def _build_pdf_result(self, path: Path | None, *, status: str, reason: str | None) -> dict[str, Any]:
        return {
            "path": path,
            "status": status,
            "reason": reason,
        }

    def _build_generation_metadata(self, pdf_result: dict[str, Any]) -> dict[str, Any]:
        pdf_status = str(pdf_result["status"])
        return {
            "report_status": "generated" if pdf_status == "generated" else "generated_html_only",
            "pdf_enabled": self.settings.base_report_pdf_enabled,
            "pdf_status": pdf_status,
            "pdf_reason": pdf_result.get("reason"),
        }

    def _write_metadata(self, metadata_path: Path, metadata: dict[str, Any]) -> None:
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_metadata(self, metadata_path: Path) -> dict[str, Any] | None:
        if not metadata_path.exists():
            return None
        try:
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

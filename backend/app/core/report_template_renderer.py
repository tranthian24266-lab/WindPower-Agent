from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from jinja2 import Environment, FileSystemLoader, select_autoescape


class ReportTemplateRenderer:
    def __init__(self, templates_path: Path):
        self.environment = Environment(
            loader=FileSystemLoader(templates_path),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render_enhanced_report(self, context: dict[str, Any]) -> str:
        template_name = self._template_name_for_task(context["case_context"]["task_type"])
        enriched = {**context, "task_profile": self._task_profile(context)}
        return self.environment.get_template(template_name).render(**enriched)

    def render_enhanced_report_docx(self, context: dict[str, Any], output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        enriched = {**context, "task_profile": self._task_profile(context)}
        with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", self._content_types_xml())
            archive.writestr("_rels/.rels", self._root_relationships_xml())
            archive.writestr("docProps/app.xml", self._app_properties_xml())
            archive.writestr("docProps/core.xml", self._core_properties_xml(enriched))
            archive.writestr("word/document.xml", self._document_xml(enriched))
            archive.writestr("word/styles.xml", self._styles_xml())
        return output_path

    def render_enhanced_report_pdf(self, context: dict[str, Any], output_path: Path) -> Path:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            from reportlab.pdfbase.pdfmetrics import registerFont
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except Exception as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(f"PDF backend 'reportlab' is unavailable: {exc}") from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        enriched = {**context, "task_profile": self._task_profile(context)}
        registerFont(UnicodeCIDFont("STSong-Light"))

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "EnhancedReportTitle",
            parent=styles["Title"],
            fontName="STSong-Light",
            fontSize=20,
            leading=26,
            textColor=colors.HexColor("#173020"),
        )
        heading_style = ParagraphStyle(
            "EnhancedReportHeading",
            parent=styles["Heading2"],
            fontName="STSong-Light",
            fontSize=13,
            leading=18,
            textColor=colors.HexColor("#173020"),
            spaceBefore=10,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "EnhancedReportBody",
            parent=styles["BodyText"],
            fontName="STSong-Light",
            fontSize=10.5,
            leading=16,
            textColor=colors.HexColor("#415244"),
        )
        meta_style = ParagraphStyle(
            "EnhancedReportMeta",
            parent=body_style,
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#66756A"),
        )

        story: list[Any] = [
            Paragraph(f"{enriched['case_id']} {enriched['task_profile']['headline']}", title_style),
            Spacer(1, 6 * mm),
            Paragraph(enriched["task_profile"]["hero_summary"], body_style),
            Spacer(1, 5 * mm),
        ]

        stat_rows = [
            ["任务类型", enriched["case_context"]["task_type"]],
            ["模型", enriched["model_context"]["model_name"]],
            ["风险等级", enriched["case_context"].get("risk_level") or "unknown"],
            [
                enriched["task_profile"]["primary_metric"]["label"],
                enriched["task_profile"]["primary_metric"]["value"],
            ],
        ]
        stat_table = Table(stat_rows, colWidths=[32 * mm, 130 * mm])
        stat_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#173020")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6FAF6")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7E1D8")),
                    ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#D7E1D8")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.extend([stat_table, Spacer(1, 5 * mm)])

        story.append(Paragraph(enriched["task_profile"]["focus_title"], heading_style))
        for item in enriched["task_profile"]["focus_points"]:
            story.append(Paragraph(f"• {item}", body_style))
        story.append(Spacer(1, 3 * mm))

        story.append(Paragraph(enriched["task_profile"]["deep_dive_title"], heading_style))
        for item in enriched["task_profile"]["deep_dive_items"]:
            story.append(Paragraph(f"{item['label']}：{item['value']}", body_style))
        story.append(Spacer(1, 4 * mm))

        for section in enriched["task_profile"]["sections"]:
            story.append(Paragraph(section["title"], heading_style))
            story.append(Paragraph(section["content"], body_style))
            refs = ", ".join(section.get("evidence_refs") or []) or "无"
            story.append(Paragraph(f"置信度：{section['confidence']} | 证据引用：{refs}", meta_style))
            story.append(Spacer(1, 2 * mm))

        story.append(Paragraph("附录指标", heading_style))
        metrics = enriched["report"].get("appendix_metrics") or []
        if metrics:
            metric_rows = [[item.get("label", ""), item.get("value", "")] for item in metrics]
            metric_table = Table(metric_rows, colWidths=[52 * mm, 110 * mm])
            metric_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7E1D8")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story.append(metric_table)
        else:
            story.append(Paragraph("暂无附录指标。", body_style))
        story.append(Spacer(1, 4 * mm))

        story.append(Paragraph("相似案例", heading_style))
        similar_cases = enriched["report"].get("similar_cases") or []
        if similar_cases:
            for item in similar_cases:
                suffix = f" (score={item['score']})" if item.get("score") is not None else ""
                story.append(Paragraph(f"{item['case_id']}：{item['summary']}{suffix}", body_style))
        else:
            story.append(Paragraph("暂无可展示的相似案例。", body_style))
        story.append(Spacer(1, 4 * mm))

        story.append(Paragraph("引用证据", heading_style))
        citations = enriched["report"].get("citations") or []
        if citations:
            for item in citations:
                story.append(Paragraph(item.get("title") or "未命名证据", body_style))
                story.append(Paragraph(item.get("excerpt") or "", body_style))
                suffix = f" | score={item['score']}" if item.get("score") is not None else ""
                story.append(
                    Paragraph(
                        f"{item.get('evidence_type') or 'unknown'} | {item.get('evidence_ref') or 'unknown'}{suffix}",
                        meta_style,
                    )
                )
                story.append(Spacer(1, 2 * mm))
        else:
            story.append(Paragraph("暂无引用证据。", body_style))

        document = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title=f"{enriched['case_id']} {enriched['task_profile']['headline']}",
        )
        document.build(story)
        return output_path

    def _template_name_for_task(self, task_type: str) -> str:
        mapping = {
            "fault_diagnosis": "enhanced_report_fault_template.html",
            "rul_prediction": "enhanced_report_rul_template.html",
            "anomaly_detection": "enhanced_report_anomaly_template.html",
        }
        return mapping.get(task_type, "enhanced_report_fault_template.html")

    def _task_profile(self, context: dict[str, Any]) -> dict[str, Any]:
        case_context = context["case_context"]
        report = context["report"]
        result = case_context["result"]
        task_type = case_context["task_type"]
        citations = report.get("citations") or []

        shared = {
            "task_type": task_type,
            "headline": self._headline_for_task(task_type),
            "hero_summary": self._hero_summary(case_context, task_type),
            "focus_title": self._focus_title_for_task(task_type),
            "focus_points": self._focus_points(case_context, task_type),
            "deep_dive_title": self._deep_dive_title_for_task(task_type),
            "deep_dive_items": self._deep_dive_items(case_context, citations, task_type),
            "sections": [
                report["case_summary"],
                report["diagnosis_conclusion"],
                report["risk_assessment"],
                report["evidence_summary"],
                report["maintenance_actions"],
                report["applicability_and_limits"],
            ],
        }
        if task_type == "fault_diagnosis":
            shared["hero_tag"] = "Fault Diagnosis"
            shared["primary_metric"] = {
                "label": "Prediction",
                "value": str(result.get("prediction") or "unknown"),
            }
        elif task_type == "rul_prediction":
            shared["hero_tag"] = "Remaining Useful Life"
            shared["primary_metric"] = {
                "label": "RUL (clipped)",
                "value": str(result.get("rul_clipped") or result.get("rul_raw") or "unknown"),
            }
        else:
            shared["hero_tag"] = "Anomaly Detection"
            shared["primary_metric"] = {
                "label": "Anomaly Ratio",
                "value": str(result.get("anomaly_ratio") or "unknown"),
            }
        return shared

    def _headline_for_task(self, task_type: str) -> str:
        mapping = {
            "fault_diagnosis": "故障诊断增强报告",
            "rul_prediction": "剩余寿命增强报告",
            "anomaly_detection": "异常检测增强报告",
        }
        return mapping.get(task_type, "增强报告")

    def _hero_summary(self, case_context: dict[str, Any], task_type: str) -> str:
        result = case_context["result"]
        if task_type == "fault_diagnosis":
            return (
                f"本次诊断判断为 {result.get('prediction') or 'unknown'}，"
                f"置信度 {result.get('confidence') or 'unknown'}，风险等级 {result.get('risk_level') or case_context.get('risk_level') or 'unknown'}。"
            )
        if task_type == "rul_prediction":
            return (
                f"当前样本的保护后 RUL 为 {result.get('rul_clipped') or 'unknown'}，"
                f"原始估计值 {result.get('rul_raw') or 'unknown'}，风险等级 {result.get('risk_level') or case_context.get('risk_level') or 'unknown'}。"
            )
        return (
            f"当前异常比例为 {result.get('anomaly_ratio') or 'unknown'}，"
            f"异常样本数 {result.get('num_anomalies') or 'unknown'}，风险等级 {result.get('risk_level') or case_context.get('risk_level') or 'unknown'}。"
        )

    def _focus_title_for_task(self, task_type: str) -> str:
        mapping = {
            "fault_diagnosis": "诊断关注点",
            "rul_prediction": "寿命关注点",
            "anomaly_detection": "监测关注点",
        }
        return mapping.get(task_type, "核心关注点")

    def _focus_points(self, case_context: dict[str, Any], task_type: str) -> list[str]:
        result = case_context["result"]
        if task_type == "fault_diagnosis":
            return [
                f"预测标签：{result.get('prediction') or 'unknown'}",
                f"模型置信度：{result.get('confidence') or 'unknown'}",
                "建议结合现场复核与部件巡检做最终处置判断。",
            ]
        if task_type == "rul_prediction":
            return [
                f"原始 RUL：{result.get('rul_raw') or 'unknown'}",
                f"展示用 RUL：{result.get('rul_clipped') or 'unknown'}",
                "建议结合趋势监测和检修窗口评估维修优先级。",
            ]
        return [
            f"异常比例：{result.get('anomaly_ratio') or 'unknown'}",
            f"异常样本数：{result.get('num_anomalies') or 'unknown'}",
            "建议结合机组工况和源机组相似性复核迁移效果。",
        ]

    def _deep_dive_title_for_task(self, task_type: str) -> str:
        mapping = {
            "fault_diagnosis": "故障证据拆解",
            "rul_prediction": "寿命证据拆解",
            "anomaly_detection": "异常证据拆解",
        }
        return mapping.get(task_type, "证据拆解")

    def _deep_dive_items(
        self,
        case_context: dict[str, Any],
        citations: list[dict[str, Any]],
        task_type: str,
    ) -> list[dict[str, str]]:
        knowledge_titles = [item.get("title") or "未命名证据" for item in citations[:2]]
        if task_type == "fault_diagnosis":
            return [
                {"label": "判断对象", "value": str(case_context["result"].get("prediction") or "unknown")},
                {"label": "优先复核", "value": "振动模式与历史相似故障的对应关系"},
                {"label": "知识引用", "value": " / ".join(knowledge_titles) or "暂无"},
            ]
        if task_type == "rul_prediction":
            return [
                {"label": "寿命信号", "value": str(case_context["result"].get("rul_clipped") or "unknown")},
                {"label": "优先复核", "value": "是否存在保护截断导致的展示偏差"},
                {"label": "知识引用", "value": " / ".join(knowledge_titles) or "暂无"},
            ]
        return [
            {"label": "异常强度", "value": str(case_context["result"].get("anomaly_ratio") or "unknown")},
            {"label": "优先复核", "value": "源机组与目标机组工况相似度"},
            {"label": "知识引用", "value": " / ".join(knowledge_titles) or "暂无"},
        ]

    def _content_types_xml(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>
"""

    def _root_relationships_xml(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""

    def _app_properties_xml(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
            xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Windpower Platform</Application>
</Properties>
"""

    def _core_properties_xml(self, context: dict[str, Any]) -> str:
        created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        case_id = escape(str(context["case_id"]))
        title = escape(str(context["task_profile"]["headline"]))
        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/"
                   xmlns:dcterms="http://purl.org/dc/terms/"
                   xmlns:dcmitype="http://purl.org/dc/dcmitype/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{case_id} {title}</dc:title>
  <dc:creator>Windpower Platform</dc:creator>
  <cp:lastModifiedBy>Windpower Platform</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{created_at}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{created_at}</dcterms:modified>
</cp:coreProperties>
"""

    def _styles_xml(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:rPr>
      <w:rFonts w:ascii="Calibri" w:eastAsia="Microsoft YaHei" w:hAnsi="Calibri"/>
      <w:sz w:val="22"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:after="220"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:sz w:val="34"/>
      <w:rFonts w:ascii="Calibri" w:eastAsia="Microsoft YaHei" w:hAnsi="Calibri"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:before="240" w:after="120"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:sz w:val="28"/>
      <w:rFonts w:ascii="Calibri" w:eastAsia="Microsoft YaHei" w:hAnsi="Calibri"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:before="180" w:after="80"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:sz w:val="24"/>
      <w:rFonts w:ascii="Calibri" w:eastAsia="Microsoft YaHei" w:hAnsi="Calibri"/>
    </w:rPr>
  </w:style>
</w:styles>
"""

    def _document_xml(self, context: dict[str, Any]) -> str:
        report = context["report"]
        case_context = context["case_context"]
        model_context = context["model_context"]
        retrieved_knowledge = context["retrieved_knowledge"]
        task_profile = context["task_profile"]

        paragraphs: list[str] = [
            self._paragraph(f"{context['case_id']} {task_profile['headline']}", style="Title"),
            self._paragraph(task_profile["hero_summary"]),
            self._paragraph(f"任务类型：{case_context['task_type']}"),
            self._paragraph(f"模型：{model_context['model_name']}"),
            self._paragraph(f"风险等级：{case_context.get('risk_level') or 'unknown'}"),
            self._paragraph(f"知识模式：{retrieved_knowledge.get('mode') or 'unknown'}"),
            self._paragraph(task_profile["focus_title"], style="Heading1"),
        ]
        for item in task_profile["focus_points"]:
            paragraphs.append(self._paragraph(f"- {item}"))

        paragraphs.append(self._paragraph(task_profile["deep_dive_title"], style="Heading1"))
        for item in task_profile["deep_dive_items"]:
            paragraphs.append(self._paragraph(f"{item['label']}：{item['value']}"))

        for section in task_profile["sections"]:
            paragraphs.append(self._paragraph(section["title"], style="Heading1"))
            paragraphs.append(self._paragraph(section["content"]))
            evidence_refs = ", ".join(section.get("evidence_refs") or [])
            paragraphs.append(self._paragraph(f"置信度：{section['confidence']} | 证据引用：{evidence_refs or '无'}"))

        paragraphs.append(self._paragraph("附录指标", style="Heading1"))
        metrics = report.get("appendix_metrics") or []
        if metrics:
            for item in metrics:
                paragraphs.append(self._paragraph(f"{item.get('label', '')}: {item.get('value', '')}"))
        else:
            paragraphs.append(self._paragraph("暂无附录指标。"))

        paragraphs.append(self._paragraph("相似案例", style="Heading1"))
        similar_cases = report.get("similar_cases") or []
        if similar_cases:
            for item in similar_cases:
                summary = item.get("summary") or ""
                score = item.get("score")
                suffix = f" (score={score})" if score is not None else ""
                paragraphs.append(self._paragraph(f"{item.get('case_id')}: {summary}{suffix}"))
        else:
            paragraphs.append(self._paragraph("暂无可展示的相似案例。"))

        paragraphs.append(self._paragraph("引用证据", style="Heading1"))
        citations = report.get("citations") or []
        if citations:
            for item in citations:
                score = item.get("score")
                score_text = f" | score={score}" if score is not None else ""
                paragraphs.append(self._paragraph(item.get("title") or "未命名证据", style="Heading2"))
                paragraphs.append(self._paragraph(item.get("excerpt") or ""))
                paragraphs.append(
                    self._paragraph(
                        f"{item.get('evidence_type') or 'unknown'} | {item.get('evidence_ref') or 'unknown'}{score_text}"
                    )
                )
        else:
            paragraphs.append(self._paragraph("暂无引用证据。"))

        body = "".join(paragraphs)
        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {body}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""

    def _paragraph(self, text: str, *, style: str | None = None) -> str:
        escaped = escape(str(text or ""))
        style_xml = f'<w:pStyle w:val="{escape(style)}"/>' if style else ""
        return (
            "<w:p>"
            f"<w:pPr>{style_xml}</w:pPr>"
            f"<w:r><w:t xml:space=\"preserve\">{escaped}</w:t></w:r>"
            "</w:p>"
        )

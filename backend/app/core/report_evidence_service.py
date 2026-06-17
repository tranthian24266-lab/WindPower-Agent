from __future__ import annotations

from math import isnan
from pathlib import Path
from typing import Any

from app.core.case_store import CaseStoreError, CaseStoreService
from app.core.model_registry import ModelRegistryError, ModelRegistryService
from app.core.retrieval_service import RetrievalService
from app.core.settings import Settings


class ReportEvidenceServiceError(RuntimeError):
    """Raised when report evidence cannot be assembled safely."""


class ReportEvidenceService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.case_store = CaseStoreService(settings.database_path)
        self.registry = ModelRegistryService(settings.resolved_littlemodel_root)
        self.retrieval_service = RetrievalService(settings)

    def collect(self, case_id: str) -> dict[str, Any]:
        case = self._load_case(case_id)
        model_meta = self._get_model_meta(case["model_id"])
        knowledge = self._retrieve_knowledge(case)
        similar_cases = self._find_similar_cases(case_id, case["task_type"])
        evidence_items = self._build_evidence_items(case, model_meta, knowledge, similar_cases)

        return {
            "case_context": {
                "case_id": case["case_id"],
                "task_type": case["task_type"],
                "model_id": case["model_id"],
                "model_name": case.get("model_name"),
                "risk_level": case.get("risk_level"),
                "created_at": case.get("created_at"),
                "original_filename": case.get("original_filename"),
                "summary": case["result"].get("summary") or "",
                "recommendation": case["result"].get("recommendation") or "",
                "result": case["result"],
                "metrics": self._build_case_metrics(case["task_type"], case["result"]),
            },
            "model_context": {
                "model_id": case["model_id"],
                "model_name": model_meta.get("model_name") or case["model_id"],
                "paper_title": model_meta.get("paper_title"),
                "dataset": model_meta.get("dataset"),
                "input_format": model_meta.get("input_format"),
                "feature_names": model_meta.get("feature_names"),
                "limitations": model_meta.get("limitations") or [],
                "readme_summary": model_meta.get("readme_summary") or "",
            },
            "retrieved_knowledge": knowledge,
            "similar_cases": similar_cases,
            "evidence_items": evidence_items,
        }

    def _load_case(self, case_id: str) -> dict[str, Any]:
        try:
            return self.case_store.get_case_detail(case_id)
        except CaseStoreError as exc:
            raise ReportEvidenceServiceError(str(exc)) from exc

    def _get_model_meta(self, model_id: str) -> dict[str, Any]:
        try:
            models = self.registry.list_models()
        except ModelRegistryError as exc:
            raise ReportEvidenceServiceError(str(exc)) from exc
        for model in models:
            if model["model_id"] == model_id:
                return model
        return {}

    def _retrieve_knowledge(self, case: dict[str, Any]) -> dict[str, Any]:
        query = " ".join(
            part
            for part in [
                str(case["task_type"]),
                str(case["result"].get("summary") or ""),
                str(case["result"].get("recommendation") or ""),
                str(case["result"].get("prediction") or ""),
                str(case["result"].get("risk_level") or case.get("risk_level") or ""),
            ]
            if part.strip()
        )
        retrieval = self.retrieval_service.search(
            query,
            case_id=case["case_id"],
            task_type=case["task_type"],
            top_k=self.settings.retrieval_top_k_default,
        )
        return {
            "mode": retrieval.mode,
            "retrieval_event_id": retrieval.retrieval_event_id,
            "chunks": [
                {
                    "chunk_id": item.chunk_id,
                    "document_id": item.document_id,
                    "title": item.title,
                    "summary": item.summary,
                    "content": item.content,
                    "source_path": item.source_path,
                    "source_type": item.source_type,
                    "chunk_index": item.chunk_index,
                    "score": round(item.score, 6),
                }
                for item in retrieval.results
            ],
        }

    def _find_similar_cases(self, case_id: str, task_type: str) -> list[dict[str, Any]]:
        items = self.case_store.list_cases(task_type=task_type)
        similar_cases: list[dict[str, Any]] = []
        for item in items:
            if item["case_id"] == case_id:
                continue
            try:
                detail = self.case_store.get_case_detail(str(item["case_id"]))
            except CaseStoreError:
                continue
            result = detail["result"]
            score = 0.0
            if detail.get("risk_level"):
                score += 0.3
            if detail.get("model_id"):
                score += 0.2
            summary = result.get("summary") or result.get("recommendation") or ""
            similar_cases.append(
                {
                    "case_id": detail["case_id"],
                    "task_type": detail["task_type"],
                    "model_id": detail["model_id"],
                    "risk_level": detail.get("risk_level"),
                    "created_at": detail.get("created_at"),
                    "summary": summary,
                    "score": round(score, 3),
                }
            )
            if len(similar_cases) >= 3:
                break
        return similar_cases

    def _build_evidence_items(
        self,
        case: dict[str, Any],
        model_meta: dict[str, Any],
        knowledge: dict[str, Any],
        similar_cases: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = [
            {
                "evidence_ref": "case_result",
                "evidence_type": "case_result",
                "source_id": case["case_id"],
                "title": f"Case {case['case_id']} result",
                "excerpt": case["result"].get("summary") or case["result"].get("recommendation") or "",
                "score": 1.0,
                "metadata": {"risk_level": case.get("risk_level"), "task_type": case["task_type"]},
            },
            {
                "evidence_ref": "model_metadata",
                "evidence_type": "model_metadata",
                "source_id": case["model_id"],
                "title": model_meta.get("model_name") or case["model_id"],
                "excerpt": model_meta.get("paper_title") or model_meta.get("dataset") or "",
                "score": 0.9,
                "metadata": {"dataset": model_meta.get("dataset"), "limitations": model_meta.get("limitations") or []},
            },
        ]

        for chunk in knowledge["chunks"]:
            items.append(
                {
                    "evidence_ref": f"knowledge:{chunk['chunk_id']}",
                    "evidence_type": "knowledge_chunk",
                    "source_id": chunk["chunk_id"],
                    "title": chunk["title"],
                    "excerpt": chunk["summary"] or chunk["content"][:180],
                    "score": chunk["score"],
                    "metadata": {
                        "source_path": chunk["source_path"],
                        "source_type": chunk["source_type"],
                        "chunk_index": chunk["chunk_index"],
                    },
                }
            )

        for similar_case in similar_cases:
            items.append(
                {
                    "evidence_ref": f"similar_case:{similar_case['case_id']}",
                    "evidence_type": "similar_case",
                    "source_id": similar_case["case_id"],
                    "title": f"Similar case {similar_case['case_id']}",
                    "excerpt": similar_case["summary"],
                    "score": similar_case["score"],
                    "metadata": {
                        "risk_level": similar_case["risk_level"],
                        "model_id": similar_case["model_id"],
                        "created_at": similar_case["created_at"],
                    },
                }
            )
        return items

    def _build_case_metrics(self, task_type: str, result: dict[str, Any]) -> list[dict[str, str]]:
        if task_type == "fault_diagnosis":
            return [
                {"label": "Prediction", "value": str(result.get("prediction", ""))},
                {"label": "Confidence", "value": self._format_value(result.get("confidence"))},
                {"label": "Risk Level", "value": str(result.get("risk_level", ""))},
            ]
        if task_type == "rul_prediction":
            return [
                {"label": "RUL Raw", "value": self._format_value(result.get("rul_raw"))},
                {"label": "RUL Clipped", "value": self._format_value(result.get("rul_clipped"))},
                {"label": "Risk Level", "value": str(result.get("risk_level", ""))},
            ]
        if task_type == "anomaly_detection":
            return [
                {"label": "Anomaly Ratio", "value": self._format_value(result.get("anomaly_ratio"))},
                {"label": "Num Anomalies", "value": self._format_value(result.get("num_anomalies"))},
                {"label": "Risk Level", "value": str(result.get("risk_level", ""))},
            ]
        return [{"label": str(key), "value": self._format_value(value)} for key, value in result.items()]

    def _format_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float) and isnan(value):
            return ""
        if isinstance(value, (dict, list)):
            return str(value)
        return str(value)

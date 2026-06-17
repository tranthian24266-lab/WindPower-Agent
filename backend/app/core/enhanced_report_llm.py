from __future__ import annotations

import inspect
import json
import re
from typing import Any

from app.core.deepseek_client import DeepSeekChatResult, DeepSeekClient, DeepSeekClientError
from app.core.settings import Settings


class EnhancedReportLLMError(RuntimeError):
    """Raised when LLM report generation cannot produce a valid payload."""


class EnhancedReportLLMService:
    SECTION_KEYS = [
        "case_summary",
        "diagnosis_conclusion",
        "risk_assessment",
        "evidence_summary",
        "maintenance_actions",
        "applicability_and_limits",
    ]

    def __init__(self, settings: Settings, deepseek_client: DeepSeekClient | None = None):
        self.settings = settings
        self.deepseek_client = deepseek_client or DeepSeekClient(settings)

    def generate_report_json(
        self,
        *,
        case_id: str,
        evidence: dict[str, Any],
        telemetry_context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        if not self.settings.deepseek_api_key:
            raise EnhancedReportLLMError("DeepSeek API key is not configured.")

        attempts: list[dict[str, Any]] = []
        usage: dict[str, Any] | None = None
        last_error: str | None = None

        base_messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": self._user_prompt(case_id=case_id, evidence=evidence)},
        ]
        repair_messages: list[dict[str, Any]] | None = None

        max_attempts = max(2, self.settings.enhanced_report_json_retry_count + 2)
        for attempt_index in range(max_attempts):
            request_kind = "repair" if repair_messages else "initial"
            messages = repair_messages or base_messages
            try:
                request_kwargs = {
                    "messages": messages,
                    "max_tokens": self._request_max_tokens(request_kind),
                    "thinking_enabled": self.settings.deepseek_thinking_enabled if request_kind == "initial" else False,
                    "reasoning_effort": self.settings.deepseek_reasoning_effort_report,
                    "response_format": {"type": "json_object"},
                    "temperature": 0.0,
                }
                signature = inspect.signature(self.deepseek_client.create_chat_completion)
                if "telemetry_context" in signature.parameters:
                    request_kwargs["telemetry_context"] = telemetry_context
                result = self.deepseek_client.create_chat_completion(**request_kwargs)
            except DeepSeekClientError as exc:
                last_error = str(exc)
                attempts.append(
                    {
                        "attempt": attempt_index + 1,
                        "request_kind": request_kind,
                        "status": "request_failed",
                        "failure_category": exc.code,
                        "error": str(exc),
                    }
                )
                if exc.code in {"empty_content", "transport_error", "http_status_error"}:
                    repair_messages = self._build_compact_repair_messages(case_id=case_id, evidence=evidence)
                    continue
                raise EnhancedReportLLMError(str(exc)) from exc

            usage = result.usage or usage
            parse_outcome = self._parse_and_normalize_result(
                result=result,
                evidence=evidence,
                attempt_index=attempt_index + 1,
                request_kind=request_kind,
            )
            attempts.append(parse_outcome["attempt"])
            if parse_outcome["payload"] is not None:
                diagnostics = {
                    "attempts": attempts,
                    "attempt_count": len(attempts),
                    "final_failure_category": None,
                    "normalized": True,
                    "repair_used": any(item["request_kind"] == "repair" for item in attempts),
                    "successful_attempt": parse_outcome["attempt"]["attempt"],
                }
                return parse_outcome["payload"], {"usage": usage or {}, "diagnostics": diagnostics}

            last_error = parse_outcome["attempt"]["error"]
            if attempt_index >= self.settings.enhanced_report_json_retry_count:
                break
            repair_messages = self._build_repair_messages(
                case_id=case_id,
                evidence=evidence,
                attempt=parse_outcome["attempt"],
                raw_content=parse_outcome["raw_content"],
            )

        diagnostics = {
            "attempts": attempts,
            "attempt_count": len(attempts),
            "final_failure_category": attempts[-1]["failure_category"] if attempts else "unknown_error",
            "normalized": False,
            "repair_used": any(item["request_kind"] == "repair" for item in attempts),
            "successful_attempt": None,
        }
        raise EnhancedReportLLMError(
            json.dumps(
                {"message": last_error or "enhanced_report_llm_failed", "diagnostics": diagnostics},
                ensure_ascii=False,
            )
        )

    def _parse_and_normalize_result(
        self,
        *,
        result: DeepSeekChatResult,
        evidence: dict[str, Any],
        attempt_index: int,
        request_kind: str,
    ) -> dict[str, Any]:
        raw_content = result.content or ""
        try:
            parsed = self._parse_json_content(raw_content)
        except DeepSeekClientError as exc:
            return {
                "payload": None,
                "raw_content": raw_content,
                "attempt": {
                    "attempt": attempt_index,
                    "request_kind": request_kind,
                    "status": "parse_failed",
                    "failure_category": exc.code,
                    "error": str(exc),
                    "raw_content_length": len(raw_content),
                    "reasoning_length": len(result.reasoning_content or ""),
                },
            }

        normalized = self._normalize_payload(parsed, evidence=evidence)
        shape_errors = self._validate_candidate_shape(normalized)
        if shape_errors:
            return {
                "payload": None,
                "raw_content": raw_content,
                "attempt": {
                    "attempt": attempt_index,
                    "request_kind": request_kind,
                    "status": "shape_failed",
                    "failure_category": "schema_validation_error",
                    "error": "; ".join(shape_errors[:8]),
                    "raw_content_length": len(raw_content),
                    "reasoning_length": len(result.reasoning_content or ""),
                },
            }

        return {
            "payload": normalized,
            "raw_content": raw_content,
            "attempt": {
                "attempt": attempt_index,
                "request_kind": request_kind,
                "status": "ok",
                "failure_category": None,
                "error": None,
                "raw_content_length": len(raw_content),
                "reasoning_length": len(result.reasoning_content or ""),
            },
        }

    def _normalize_payload(self, payload: dict[str, Any], *, evidence: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        section_titles = self._section_titles(evidence["case_context"]["task_type"])
        default_evidence_refs = self._default_section_evidence_refs(evidence)

        for section_key in self.SECTION_KEYS:
            normalized[section_key] = self._normalize_section(
                value=normalized.get(section_key),
                default_title=section_titles[section_key],
                default_refs=default_evidence_refs[section_key],
            )

        normalized["similar_cases"] = self._normalize_similar_cases(normalized.get("similar_cases"))
        normalized["appendix_metrics"] = self._normalize_appendix_metrics(normalized.get("appendix_metrics"))
        normalized["citations"] = self._normalize_citations(
            normalized.get("citations"),
            evidence_items=evidence.get("evidence_items") or [],
        )
        return normalized

    def _parse_json_content(self, content: str) -> dict[str, Any]:
        normalized = content.strip()
        if normalized.startswith("```"):
            normalized = normalized.strip("`")
            if normalized.startswith("json"):
                normalized = normalized[4:]
            normalized = normalized.strip()

        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError as exc:
            repaired = self._repair_json_candidate(normalized)
            if repaired and repaired != normalized:
                try:
                    parsed = json.loads(repaired)
                except json.JSONDecodeError:
                    raise DeepSeekClientError(
                        f"DeepSeek JSON output parsing failed: {exc}",
                        code="json_parse_error",
                    ) from exc
            else:
                raise DeepSeekClientError(
                    f"DeepSeek JSON output parsing failed: {exc}",
                    code="json_parse_error",
                ) from exc

        if not isinstance(parsed, dict):
            raise DeepSeekClientError("DeepSeek JSON output must be a JSON object.", code="invalid_json_object")
        return parsed

    def _repair_json_candidate(self, content: str) -> str | None:
        candidate = content.strip()
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1:
            candidate = candidate[start : end + 1] if end > start else candidate[start:]

        candidate = candidate.replace("\r", " ").replace("\t", " ")
        candidate = candidate.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        candidate = re.sub(r",(\s*[}\]])", r"\1", candidate)
        candidate = re.sub(r"\n+", " ", candidate)
        candidate = candidate.rstrip(", ")
        candidate = self._close_json_candidate(candidate)
        candidate = re.sub(r",(\s*[}\]])", r"\1", candidate)
        return candidate.strip() if candidate.strip() else None

    def _close_json_candidate(self, candidate: str) -> str:
        stack: list[str] = []
        in_string = False
        escaped = False

        for char in candidate:
            if in_string:
                if escaped:
                    escaped = False
                    continue
                if char == "\\":
                    escaped = True
                    continue
                if char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                stack.append("}")
            elif char == "[":
                stack.append("]")
            elif char in {"}", "]"} and stack and stack[-1] == char:
                stack.pop()

        repaired = candidate
        if in_string:
            repaired += '"'
        if stack:
            repaired += "".join(reversed(stack))
        return repaired

    def _normalize_section(
        self,
        *,
        value: Any,
        default_title: str,
        default_refs: list[str],
    ) -> dict[str, Any]:
        source = value if isinstance(value, dict) else {}
        title = str(source.get("title") or default_title).strip() or default_title
        content = str(source.get("content") or "").strip()
        confidence = self._normalize_confidence(source.get("confidence"))
        evidence_refs = (
            self._normalize_string_list(source.get("evidence_refs"))
            if "evidence_refs" in source
            else list(default_refs)
        )
        return {
            "title": title,
            "content": content,
            "confidence": confidence,
            "evidence_refs": evidence_refs,
        }

    def _normalize_similar_cases(self, value: Any) -> list[dict[str, Any]]:
        if isinstance(value, dict):
            items = [value]
        elif isinstance(value, list):
            items = value
        elif value:
            items = [value]
        else:
            items = []

        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(items, start=1):
            if isinstance(item, dict):
                summary = str(item.get("summary") or item.get("content") or item.get("title") or "").strip()
                if not summary:
                    continue
                case_id = str(item.get("case_id") or item.get("id") or f"similar_case_{index}").strip()
                normalized.append(
                    {
                        "case_id": case_id or f"similar_case_{index}",
                        "summary": summary,
                        "score": self._normalize_optional_score(item.get("score")),
                    }
                )
            elif isinstance(item, str) and item.strip():
                normalized.append(
                    {
                        "case_id": f"similar_case_{index}",
                        "summary": item.strip(),
                        "score": None,
                    }
                )
        return normalized

    def _normalize_appendix_metrics(self, value: Any) -> list[dict[str, str]]:
        if isinstance(value, dict):
            return [
                {"label": str(label).strip(), "value": self._stringify_metric(metric_value)}
                for label, metric_value in value.items()
                if str(label).strip()
            ]

        if not isinstance(value, list):
            return []

        normalized: list[dict[str, str]] = []
        for item in value:
            if isinstance(item, dict):
                label = str(item.get("label") or item.get("name") or item.get("metric") or "").strip()
                metric_value = item.get("value")
                if not label:
                    if len(item) == 1:
                        key, only_value = next(iter(item.items()))
                        label = str(key).strip()
                        metric_value = only_value
                    else:
                        continue
                normalized.append({"label": label, "value": self._stringify_metric(metric_value)})
            elif isinstance(item, str) and ":" in item:
                label, metric_value = item.split(":", 1)
                normalized.append({"label": label.strip(), "value": metric_value.strip()})
        return normalized

    def _normalize_citations(self, value: Any, *, evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        reference_map = {str(item["evidence_ref"]): item for item in evidence_items if item.get("evidence_ref")}

        if isinstance(value, dict):
            items = [value]
        elif isinstance(value, list):
            items = value
        elif value:
            items = [value]
        else:
            items = []

        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(items, start=1):
            if isinstance(item, dict):
                evidence_ref = str(item.get("evidence_ref") or item.get("ref") or "").strip()
                matched = reference_map.get(evidence_ref) if evidence_ref else None
                title = str(item.get("title") or (matched or {}).get("title") or f"Citation {index}").strip()
                excerpt = str(item.get("excerpt") or item.get("summary") or (matched or {}).get("excerpt") or "").strip()
                evidence_type = str(
                    item.get("evidence_type") or (matched or {}).get("evidence_type") or "knowledge_chunk"
                ).strip()
                if not excerpt:
                    excerpt = title
                normalized.append(
                    {
                        "evidence_ref": evidence_ref or str((matched or {}).get("evidence_ref") or f"citation_{index}"),
                        "title": title,
                        "excerpt": excerpt,
                        "evidence_type": evidence_type,
                        "score": self._normalize_optional_score(item.get("score") or (matched or {}).get("score")),
                    }
                )
            elif isinstance(item, str) and item.strip():
                matched = reference_map.get(item.strip())
                normalized.append(
                    {
                        "evidence_ref": str((matched or {}).get("evidence_ref") or f"citation_{index}"),
                        "title": str((matched or {}).get("title") or item.strip()[:80]),
                        "excerpt": str((matched or {}).get("excerpt") or item.strip()),
                        "evidence_type": str((matched or {}).get("evidence_type") or "knowledge_chunk"),
                        "score": self._normalize_optional_score((matched or {}).get("score")),
                    }
                )
        return normalized

    def _validate_candidate_shape(self, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for section_key in self.SECTION_KEYS:
            section = payload.get(section_key)
            if not isinstance(section, dict):
                errors.append(f"{section_key} must be an object")
                continue
            if not isinstance(section.get("title"), str) or not section.get("title", "").strip():
                errors.append(f"{section_key}.title must be a non-empty string")
            if not isinstance(section.get("content"), str) or not section.get("content", "").strip():
                errors.append(f"{section_key}.content must be a non-empty string")
            confidence = section.get("confidence")
            if not isinstance(confidence, (int, float)):
                errors.append(f"{section_key}.confidence must be numeric")
            elif not 0.0 <= float(confidence) <= 1.0:
                errors.append(f"{section_key}.confidence must be between 0 and 1")
            evidence_refs = section.get("evidence_refs")
            if not isinstance(evidence_refs, list) or any(not isinstance(item, str) or not item.strip() for item in evidence_refs):
                errors.append(f"{section_key}.evidence_refs must be a list[str]")

        if not isinstance(payload.get("similar_cases"), list):
            errors.append("similar_cases must be a list")
        if not isinstance(payload.get("appendix_metrics"), list):
            errors.append("appendix_metrics must be a list")
        if not isinstance(payload.get("citations"), list):
            errors.append("citations must be a list")
        return errors

    def _build_repair_messages(
        self,
        *,
        case_id: str,
        evidence: dict[str, Any],
        attempt: dict[str, Any],
        raw_content: str,
    ) -> list[dict[str, Any]]:
        validation_error = attempt.get("error") or "schema validation failed"
        compact_evidence = self._compact_evidence(evidence)
        return [
            {"role": "system", "content": self._system_prompt()},
            {
                "role": "user",
                "content": "\n\n".join(
                    [
                        f"Case ID: {case_id}",
                        "The previous JSON response was invalid. Return only one corrected JSON object.",
                        f"Invalid reason: {validation_error}",
                        "Do not add markdown, explanation, or code fences.",
                        "Use the schema and field names exactly as requested.",
                        "Keep each section content concise, ideally under 120 Chinese characters.",
                        "Keep citations short and do not include unnecessary nested metadata.",
                        "Compact evidence package:",
                        json.dumps(compact_evidence, ensure_ascii=False, indent=2),
                        "Previous invalid JSON candidate:",
                        raw_content[:5000] if raw_content.strip() else "{}",
                    ]
                ),
            },
        ]

    def _build_compact_repair_messages(self, *, case_id: str, evidence: dict[str, Any]) -> list[dict[str, Any]]:
        compact_evidence = self._compact_evidence(evidence)
        return [
            {"role": "system", "content": self._system_prompt()},
            {
                "role": "user",
                "content": "\n\n".join(
                    [
                        f"Case ID: {case_id}",
                        "Return only one JSON object that matches the requested schema.",
                        "The previous attempt returned empty content or failed in transport recovery.",
                        "Keep wording concise and use only the evidence below.",
                        "Keep each section content under 120 Chinese characters whenever possible.",
                        json.dumps(compact_evidence, ensure_ascii=False, indent=2),
                    ]
                ),
            },
        ]

    def _compact_evidence(self, evidence: dict[str, Any]) -> dict[str, Any]:
        case_context = evidence.get("case_context") or {}
        model_context = evidence.get("model_context") or {}
        retrieved_knowledge = evidence.get("retrieved_knowledge") or {}
        evidence_items = [
            {
                "evidence_ref": item.get("evidence_ref"),
                "title": item.get("title"),
                "excerpt": item.get("excerpt"),
                "evidence_type": item.get("evidence_type"),
                "score": item.get("score"),
            }
            for item in (evidence.get("evidence_items") or [])[:6]
        ]

        return {
            "case_context": {
                "task_type": case_context.get("task_type"),
                "summary": case_context.get("summary"),
                "risk_level": case_context.get("risk_level"),
                "recommendation": case_context.get("recommendation"),
                "metrics": (case_context.get("metrics") or [])[:4],
                "result": case_context.get("result"),
            },
            "model_context": {
                "model_name": model_context.get("model_name"),
                "paper_title": model_context.get("paper_title"),
                "dataset": model_context.get("dataset"),
                "limitations": (model_context.get("limitations") or [])[:3],
            },
            "retrieved_knowledge": {
                "chunks": [
                    {
                        "title": chunk.get("title"),
                        "summary": chunk.get("summary"),
                        "source_type": chunk.get("source_type"),
                        "task_type": chunk.get("task_type"),
                        "score": chunk.get("score"),
                    }
                    for chunk in retrieved_knowledge.get("chunks", [])[:3]
                ],
                "knowledge_mode": retrieved_knowledge.get("knowledge_mode"),
            },
            "similar_cases": [
                {
                    "case_id": item.get("case_id"),
                    "summary": item.get("summary"),
                    "score": item.get("score"),
                }
                for item in (evidence.get("similar_cases") or [])[:3]
            ],
            "evidence_items": evidence_items,
        }

    def _normalize_confidence(self, value: Any) -> float:
        try:
            normalized = float(value)
        except (TypeError, ValueError):
            return 0.58
        return round(min(max(normalized, 0.0), 1.0), 2)

    def _normalize_optional_score(self, value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return round(float(value), 4)
        except (TypeError, ValueError):
            return None

    def _normalize_string_list(self, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _stringify_metric(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.4f}".rstrip("0").rstrip(".")
        return str(value)

    def _request_max_tokens(self, request_kind: str) -> int:
        configured = max(512, int(self.settings.deepseek_max_tokens_report))
        if request_kind == "initial":
            return configured
        return min(configured, 1600)

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

    def _default_section_evidence_refs(self, evidence: dict[str, Any]) -> dict[str, list[str]]:
        knowledge_refs = [
            item["evidence_ref"]
            for item in evidence.get("evidence_items") or []
            if item.get("evidence_type") == "knowledge_chunk"
        ]
        similar_case_refs = [
            item["evidence_ref"]
            for item in evidence.get("evidence_items") or []
            if item.get("evidence_type") == "similar_case"
        ]
        return {
            "case_summary": ["case_result"],
            "diagnosis_conclusion": ["case_result", "model_metadata"],
            "risk_assessment": ["case_result", *(similar_case_refs[:2] or knowledge_refs[:1])],
            "evidence_summary": knowledge_refs[:4] or ["model_metadata"],
            "maintenance_actions": ["case_result", "model_metadata"],
            "applicability_and_limits": ["model_metadata", *(knowledge_refs[:1])],
        }

    def _system_prompt(self) -> str:
        return "\n".join(
            [
                "You are generating a wind-power enhanced diagnostic report.",
                "Return exactly one JSON object and nothing else.",
                "Do not output markdown, code fences, explanations, or prose outside JSON.",
                "The JSON object must contain these top-level keys:",
                "case_summary, diagnosis_conclusion, risk_assessment, evidence_summary, maintenance_actions, applicability_and_limits, similar_cases, appendix_metrics, citations.",
                "Each section object must include: title, content, confidence, evidence_refs.",
                "confidence must be a number between 0 and 1.",
                "similar_cases must be an array of objects: {case_id, summary, score}.",
                "appendix_metrics must be an array of objects: {label, value}.",
                "citations must be an array of objects: {evidence_ref, title, excerpt, evidence_type, score}.",
                "If evidence is weak or incomplete, lower confidence and state the limitation in content.",
                "Never invent unavailable evidence references.",
                "Keep each content field concise, ideally within 120 Chinese characters.",
                "Prefer at most 3 citations unless more are strictly necessary.",
                "Minimal valid JSON example:",
                json.dumps(
                    {
                        "case_summary": {
                            "title": "案例摘要",
                            "content": "这里写一句基于证据的摘要。",
                            "confidence": 0.72,
                            "evidence_refs": ["case_result"],
                        },
                        "diagnosis_conclusion": {
                            "title": "诊断结论",
                            "content": "这里写结论。",
                            "confidence": 0.68,
                            "evidence_refs": ["case_result", "model_metadata"],
                        },
                        "risk_assessment": {
                            "title": "风险评估",
                            "content": "这里写风险评估。",
                            "confidence": 0.66,
                            "evidence_refs": ["case_result"],
                        },
                        "evidence_summary": {
                            "title": "证据摘要",
                            "content": "这里写证据摘要。",
                            "confidence": 0.7,
                            "evidence_refs": ["knowledge_chunk_1"],
                        },
                        "maintenance_actions": {
                            "title": "维护建议",
                            "content": "这里写维护建议。",
                            "confidence": 0.63,
                            "evidence_refs": ["case_result"],
                        },
                        "applicability_and_limits": {
                            "title": "适用边界与限制",
                            "content": "这里写限制说明。",
                            "confidence": 0.74,
                            "evidence_refs": ["model_metadata"],
                        },
                        "similar_cases": [{"case_id": "example_case", "summary": "相似案例摘要", "score": 0.55}],
                        "appendix_metrics": [{"label": "Risk Level", "value": "warning"}],
                        "citations": [
                            {
                                "evidence_ref": "case_result",
                                "title": "Case result",
                                "excerpt": "关键证据摘录",
                                "evidence_type": "case_result",
                                "score": 1.0,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
            ]
        )

    def _user_prompt(self, *, case_id: str, evidence: dict[str, Any]) -> str:
        return "\n\n".join(
            [
                f"Case ID: {case_id}",
                "Generate an enhanced report JSON using only the evidence package below.",
                "Return only JSON.",
                json.dumps(self._compact_evidence(evidence), ensure_ascii=False, indent=2),
            ]
        )

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

from app.core.case_store import CaseStoreError, CaseStoreService
from app.core.agent_runtime.run_manager import RunManager
from app.core.deepseek_client import DeepSeekChatResult, DeepSeekClient, DeepSeekClientError
from app.core.model_registry import ModelRegistryError, ModelRegistryService
from app.core.rag_service import RAGService
from app.core.settings import Settings
from app.core.telemetry_service import TelemetryService


class AgentServiceError(RuntimeError):
    """Raised when chat service cannot answer safely."""


class AgentService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.case_store = CaseStoreService(settings.database_path)
        self.registry = ModelRegistryService(settings.resolved_littlemodel_root)
        self.rag_service = RAGService(settings)
        self.deepseek_client = DeepSeekClient(settings)
        self.telemetry = TelemetryService(settings)
        self._last_deepseek_result: DeepSeekChatResult | None = None
        self._current_run_id: str | None = None

    def answer(
        self,
        case_id: str,
        question: str,
        session_id: str | None = None,
        *,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        self._current_run_id = run_id
        case = self._load_case(case_id)
        model_meta = self._load_model_meta(case["model_id"])
        session_id = self.case_store.create_chat_session(case_id, session_id)
        self.case_store.save_chat_message(
            session_id,
            "user",
            question,
            message_metadata={"run_id": run_id} if run_id else None,
        )

        self._last_deepseek_result = None
        rag_answer = self.rag_service.answer(
            case=case,
            model_meta=model_meta,
            question=question,
            answer_builder=lambda knowledge_context: self._generate_answer(
                case,
                model_meta,
                question,
                knowledge_context_override=knowledge_context,
            ),
        )
        answer = self._apply_answer_guardrails(case, rag_answer.answer, rag_answer.citations)
        assistant_metadata = self._build_assistant_metadata(rag_answer.mode, run_id=run_id)
        self.case_store.save_chat_message(
            session_id,
            "assistant",
            answer,
            citations=rag_answer.citations,
            knowledge_mode=rag_answer.knowledge_mode,
            retrieval_event_id=rag_answer.retrieval_event_id,
            message_metadata=assistant_metadata,
        )
        self.telemetry.record(
            "chat_answer_summary",
            {
                "case_id": case_id,
                "session_id": session_id,
                "run_id": run_id,
                **self._runtime_trace_context(run_id),
                "mode": rag_answer.mode,
                "knowledge_mode": rag_answer.knowledge_mode,
                "citation_count": len(rag_answer.citations),
                "retrieval_event_id": rag_answer.retrieval_event_id,
                "usage": (
                    self._last_deepseek_result.usage
                    if self._last_deepseek_result and self._last_deepseek_result.usage
                    else {}
                ),
            },
        )

        return {
            "status": "ok",
            "case_id": case_id,
            "session_id": session_id,
            "run_id": run_id,
            "answer": answer,
            "mode": rag_answer.mode,
            "citations": rag_answer.citations,
            "retrieval_event_id": rag_answer.retrieval_event_id,
            "knowledge_mode": rag_answer.knowledge_mode,
        }

    def _apply_answer_guardrails(
        self,
        case: dict[str, Any],
        answer: str,
        citations: list[dict[str, Any]],
    ) -> str:
        risk_level = str(case.get("risk_level") or case.get("result", {}).get("risk_level") or "").strip().lower()
        if risk_level not in {"warning", "high", "critical"}:
            return answer
        if citations:
            return answer
        note = "高风险案例当前未绑定外部证据引用，请以增强报告或人工复核结果作为维护处置依据。"
        if note in answer:
            return answer
        return f"{answer}\n\n{note}".strip()

    def get_history(self, case_id: str) -> dict[str, Any]:
        self._load_case(case_id)
        return {
            "status": "ok",
            "case_id": case_id,
            "messages": self.case_store.get_chat_history(case_id),
        }

    def _generate_answer(
        self,
        case: dict[str, Any],
        model_meta: dict[str, Any],
        question: str,
        knowledge_context_override: str | None = None,
    ) -> tuple[str, str]:
        mode = (self.settings.agent_mode or "auto").lower()

        if self._should_use_deepseek(mode):
            try:
                return (
                    self._build_deepseek_answer(
                        case,
                        model_meta,
                        question,
                        knowledge_context_override=knowledge_context_override,
                    ),
                    "deepseek_api",
                )
            except AgentServiceError:
                if mode == "api":
                    raise
            except Exception as exc:  # pragma: no cover - defensive catch for network/runtime issues
                if mode == "api":
                    raise AgentServiceError(f"DeepSeek API request failed: {exc}") from exc

        return (
            self._build_rule_answer(
                case,
                model_meta,
                question,
                knowledge_context_override=knowledge_context_override,
            ),
            "rule_based_local",
        )

    def _should_use_deepseek(self, mode: str) -> bool:
        if mode == "local":
            return False
        return bool(self.settings.deepseek_api_key)

    def _build_deepseek_answer(
        self,
        case: dict[str, Any],
        model_meta: dict[str, Any],
        question: str,
        *,
        knowledge_context_override: str | None = None,
    ) -> str:
        system_prompt = (
            "你是风电智能诊断助手。"
            "你只能基于给定的案例结果、模型元信息和本地知识库片段回答。"
            "如果证据不足，必须明确说明不确定，不要编造未给出的设备状态、原因或数值。"
            "请始终使用中文，优先给出：结果解读、风险判断、维护建议、适用边界。"
        )
        user_prompt = self._build_llm_context(
            case,
            model_meta,
            question,
            knowledge_context_override=knowledge_context_override,
        )

        try:
            request_kwargs = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": self.settings.deepseek_max_tokens_chat,
                "thinking_enabled": self.settings.deepseek_thinking_enabled,
                "reasoning_effort": self.settings.deepseek_reasoning_effort,
                "response_format": {"type": "json_object"} if self.settings.deepseek_chat_json_output_enabled else None,
            }
            signature = inspect.signature(self.deepseek_client.create_chat_completion)
            if "telemetry_context" in signature.parameters:
                request_kwargs["telemetry_context"] = {
                    "case_id": case["case_id"],
                    "run_id": self._current_run_id,
                    **self._runtime_trace_context(self._current_run_id),
                }
            result = self.deepseek_client.create_chat_completion(**request_kwargs)
        except DeepSeekClientError as exc:
            raise AgentServiceError(str(exc)) from exc

        self._last_deepseek_result = result
        return result.content

    def _build_llm_context(
        self,
        case: dict[str, Any],
        model_meta: dict[str, Any],
        question: str,
        *,
        knowledge_context_override: str | None = None,
    ) -> str:
        case_context = {
            "case_id": case["case_id"],
            "task_type": case["task_type"],
            "risk_level": case.get("risk_level"),
            "model_id": case["model_id"],
            "model_name": case.get("model_name"),
            "original_filename": case.get("original_filename"),
            "created_at": case.get("created_at"),
            "result": case["result"],
        }
        model_context = {
            "model_name": model_meta.get("model_name", case["model_id"]),
            "paper_title": model_meta.get("paper_title"),
            "dataset": model_meta.get("dataset"),
            "input_format": model_meta.get("input_format"),
            "output_labels": model_meta.get("output_labels"),
            "feature_names": model_meta.get("feature_names"),
            "threshold": model_meta.get("threshold"),
            "limitations": model_meta.get("limitations") or [],
        }
        knowledge_context = self._knowledge_context(case["task_type"], knowledge_context_override=knowledge_context_override)

        return "\n\n".join(
            [
                f"用户问题：\n{question}",
                "案例结果：\n" + json.dumps(case_context, ensure_ascii=False, indent=2),
                "模型信息：\n" + json.dumps(model_context, ensure_ascii=False, indent=2),
                "知识库片段：\n" + knowledge_context,
            ]
        )

    def _knowledge_context(self, task_type: str, *, knowledge_context_override: str | None = None) -> str:
        if knowledge_context_override:
            return knowledge_context_override
        filename_map = {
            "fault_diagnosis": "fault_diagnosis.md",
            "rul_prediction": "rul_prediction.md",
            "anomaly_detection": "anomaly_detection.md",
        }
        filename = filename_map.get(task_type)
        if not filename:
            return "暂无知识库片段。"

        parts = [
            self._read_markdown_excerpt(self.settings.knowledge_base_path / "domain_knowledge" / filename),
            self._read_markdown_excerpt(self.settings.knowledge_base_path / "models" / filename),
        ]
        joined = "\n\n".join(part for part in parts if part)
        return joined or "暂无知识库片段。"

    def _read_markdown_excerpt(self, path: Path) -> str:
        if not path.exists():
            return ""
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
        useful_lines = [line for line in lines if line and not line.startswith("#")]
        return "\n".join(useful_lines[:8])

    def _load_case(self, case_id: str) -> dict[str, Any]:
        try:
            return self.case_store.get_case_detail(case_id)
        except CaseStoreError as exc:
            raise AgentServiceError(str(exc)) from exc

    def _load_model_meta(self, model_id: str) -> dict[str, Any]:
        try:
            for model in self.registry.list_models():
                if model["model_id"] == model_id:
                    return model
        except ModelRegistryError as exc:
            raise AgentServiceError(str(exc)) from exc
        return {}

    def _build_rule_answer(
        self,
        case: dict[str, Any],
        model_meta: dict[str, Any],
        question: str,
        *,
        knowledge_context_override: str | None = None,
    ) -> str:
        result = case["result"]
        lead = "当前未连通可用的大模型接口，本次回答基于本地案例结果、模型卡和知识库片段自动生成。"
        question_line = f"问题：{question}"

        if case["task_type"] == "fault_diagnosis":
            body = (
                f"该案例的 `prediction` 为 `{result.get('prediction')}`，`confidence` 为 `{result.get('confidence')}`，"
                f"风险等级为 `{result.get('risk_level')}`。"
                f"建议：{result.get('recommendation', '请结合现场复核流程进一步确认。')}"
            )
        elif case["task_type"] == "rul_prediction":
            body = (
                f"该案例的 `RUL` 原始预测值为 `{result.get('rul_raw')}`，展示值为 `{result.get('rul_clipped')}`，"
                f"风险等级为 `{result.get('risk_level')}`。"
                f"建议：{result.get('recommendation', '请结合后续监测点继续观察。')}"
            )
        else:
            body = (
                f"该案例的 `anomaly_ratio` 为 `{result.get('anomaly_ratio')}`，`threshold` 为 `{result.get('threshold')}`，"
                f"异常样本数为 `{result.get('num_anomalies')}`，风险等级为 `{result.get('risk_level')}`。"
                f"建议：{result.get('recommendation', '请结合 SCADA 趋势进一步排查。')}"
            )

        model_line = (
            f"模型信息：{model_meta.get('model_name', case['model_id'])}。"
            f"数据集：{model_meta.get('dataset', '未提供')}。"
        )
        limitation_line = ""
        limitations = model_meta.get("limitations") or []
        if limitations:
            limitation_line = f"适用边界：{limitations[0]}"

        knowledge_line = self._knowledge_excerpt(
            case["task_type"],
            knowledge_context_override=knowledge_context_override,
        )
        return "\n\n".join([lead, question_line, body, model_line, limitation_line, knowledge_line]).strip()

    def _knowledge_excerpt(self, task_type: str, *, knowledge_context_override: str | None = None) -> str:
        if knowledge_context_override:
            excerpt = " ".join(line.strip() for line in knowledge_context_override.splitlines() if line.strip())
            return f"知识库提示：{excerpt[:400]}"
        filename_map = {
            "fault_diagnosis": "fault_diagnosis.md",
            "rul_prediction": "rul_prediction.md",
            "anomaly_detection": "anomaly_detection.md",
        }
        path = self.settings.knowledge_base_path / "domain_knowledge" / filename_map[task_type]
        if not path.exists():
            return "知识库提示：当前未加载额外领域知识。"

        content = path.read_text(encoding="utf-8").splitlines()
        lines = [line.strip() for line in content if line.strip() and not line.startswith("#")]
        excerpt = " ".join(lines[:3])
        return f"知识库提示：{excerpt}"

    def _build_assistant_metadata(self, mode: str, run_id: str | None = None) -> dict[str, Any] | None:
        if not self._last_deepseek_result:
            metadata: dict[str, Any] = {"mode": mode}
            if run_id:
                metadata["run_id"] = run_id
            return metadata
        metadata: dict[str, Any] = {"mode": mode}
        if run_id:
            metadata["run_id"] = run_id
        if self._last_deepseek_result.reasoning_content:
            metadata["reasoning_content"] = self._last_deepseek_result.reasoning_content
        if self._last_deepseek_result.usage:
            metadata["usage"] = self._last_deepseek_result.usage
        return metadata

    def _runtime_trace_context(self, run_id: str | None) -> dict[str, Any]:
        if not run_id:
            return {}
        detail = RunManager(self.settings.database_path).get_run_detail(run_id)
        if not detail:
            return {}
        trace_id = detail.get("trace_id")
        return {"trace_id": trace_id} if trace_id else {}

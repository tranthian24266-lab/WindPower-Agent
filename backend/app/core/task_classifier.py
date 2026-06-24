from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.input_profiler import InputProfile, InputProfilerService
from app.core.model_registry import ModelRegistryService


@dataclass(frozen=True)
class TaskCandidate:
    task_type: str
    model_id: str
    model_name: str | None
    score: float
    evidence: list[str]
    mismatches: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "score": round(self.score, 4),
            "evidence": self.evidence,
            "mismatches": self.mismatches,
        }


@dataclass(frozen=True)
class TaskClassification:
    status: str
    confidence: float
    selected_task_type: str | None
    selected_model_id: str | None
    evidence: list[str]
    candidates: list[TaskCandidate]
    input_profile: InputProfile

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "confidence": round(self.confidence, 4),
            "selected_task_type": self.selected_task_type,
            "selected_model_id": self.selected_model_id,
            "evidence": self.evidence,
            "candidates": [candidate.as_dict() for candidate in self.candidates],
            "input_profile": self.input_profile.as_dict(),
        }


class TaskClassifierService:
    auto_threshold = 0.85
    confirmation_threshold = 0.55
    minimum_margin = 0.20

    def __init__(self, littlemodel_root: Path):
        self.registry = ModelRegistryService(littlemodel_root)
        self.profiler = InputProfilerService()

    def classify(self, input_path: Path) -> TaskClassification:
        profile = self.profiler.profile(input_path)
        scored = [self._score_model(profile, model) for model in self.registry.list_models() if model.get("status") == "active"]
        best_by_task: dict[str, TaskCandidate] = {}
        for candidate in scored:
            current = best_by_task.get(candidate.task_type)
            if current is None or candidate.score > current.score:
                best_by_task[candidate.task_type] = candidate
        ranked = sorted(best_by_task.values(), key=lambda item: (-item.score, item.task_type))
        if not ranked:
            return TaskClassification("unsupported", 0.0, None, None, [], [], profile)
        best = ranked[0]
        margin = best.score - (ranked[1].score if len(ranked) > 1 else 0.0)
        selected = best.score >= self.auto_threshold and margin >= self.minimum_margin
        status = "selected" if selected else "needs_confirmation" if best.score >= self.confirmation_threshold else "unsupported"
        return TaskClassification(status, best.score, best.task_type if selected else None, best.model_id if selected else None, best.evidence, ranked, profile)

    def _score_model(self, profile: InputProfile, model: dict[str, Any]) -> TaskCandidate:
        score, evidence, mismatches = _score_contract(profile, model.get("input_contract") or {})
        return TaskCandidate(str(model["task_type"]), str(model["model_id"]), model.get("model_name"), min(score, 1.0), evidence, mismatches)


def _score_contract(profile: InputProfile, contract: dict[str, Any]) -> tuple[float, list[str], list[str]]:
    score = 0.0
    evidence: list[str] = []
    mismatches: list[str] = []
    suffixes = [str(value).lower() for value in contract.get("accepted_suffixes") or []]
    if profile.suffix in suffixes:
        score += 0.35
        evidence.append(f"文件扩展名 {profile.suffix} 符合模型输入契约")
    else:
        mismatches.append(f"文件扩展名 {profile.suffix} 不在 {suffixes}")
    expected_containers = contract.get("container_types") or [contract.get("container_type")]
    expected_containers = [value for value in expected_containers if value]
    if profile.container_type in expected_containers:
        score += 0.20
        evidence.append(f"数据容器类型为 {profile.container_type}")
    elif expected_containers:
        mismatches.append(f"数据容器类型需要 {expected_containers}")
    score += _score_columns(profile, contract, evidence, mismatches)
    score += _score_arrays(profile, contract, evidence, mismatches)
    return score, evidence, mismatches


def _score_columns(profile: InputProfile, contract: dict[str, Any], evidence: list[str], mismatches: list[str]) -> float:
    required = {str(value) for value in contract.get("required_columns") or []}
    if not required:
        return 0.0
    ratio = len(required.intersection(profile.columns)) / len(required)
    if ratio:
        evidence.append(f"必需字段匹配率为 {ratio:.0%}")
    if ratio < float(contract.get("minimum_required_column_ratio") or 1.0):
        mismatches.append(f"必需字段匹配率只有 {ratio:.0%}")
    return 0.45 * ratio


def _score_arrays(profile: InputProfile, contract: dict[str, Any], evidence: list[str], mismatches: list[str]) -> float:
    score = 0.0
    required_keys = {str(value) for value in contract.get("required_array_keys") or []}
    alternative_keys = {str(value) for value in contract.get("alternative_array_keys") or []}
    profile_keys = set(profile.array_keys)
    if required_keys:
        ratio = len(required_keys.intersection(profile_keys)) / len(required_keys)
        score += 0.45 * ratio
        if ratio == 1.0:
            evidence.append(f"检测到必需数据键：{', '.join(sorted(required_keys))}")
        else:
            mismatches.append(f"缺少数据键：{', '.join(sorted(required_keys - profile_keys))}")
    elif alternative_keys and alternative_keys.intersection(profile_keys):
        score += 0.45
        evidence.append(f"检测到兼容数据键：{', '.join(sorted(alternative_keys.intersection(profile_keys)))}")
    last_dimension = contract.get("required_last_dimension")
    if last_dimension is not None and profile.array_shape:
        if profile.array_shape[-1] == int(last_dimension):
            score += 0.45
            evidence.append(f"数组最后一维为 {last_dimension}")
        else:
            mismatches.append(f"数组最后一维不是 {last_dimension}")
    return score

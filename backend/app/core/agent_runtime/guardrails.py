from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


class GuardrailViolationError(RuntimeError):
    """Raised when a runtime action violates a non-recoverable guardrail."""


class ToolAccessDeniedError(GuardrailViolationError):
    """Raised when a tool is invoked outside its allowed run types."""


@dataclass
class ReportGuardrailResult:
    publication_status: str
    violations: list[dict[str, Any]]
    review_required: bool

    def to_metadata(self) -> dict[str, Any]:
        return {
            "publication_status": self.publication_status,
            "review_required": self.review_required,
            "violation_count": len(self.violations),
            "violations": self.violations,
        }


class AgentGuardrails:
    HIGH_RISK_LEVELS = {"warning", "high", "critical"}
    HIGH_RISK_SECTIONS = {"risk_assessment", "maintenance_actions"}
    GROUNDING_EVIDENCE_TYPES = {"case_result", "knowledge_chunk", "similar_case"}

    def validate_tool_access(
        self,
        *,
        tool_name: str,
        run_type: str | None,
        allowed_run_types: Iterable[str] | None,
    ) -> None:
        allowed = {str(item).strip() for item in (allowed_run_types or []) if str(item).strip()}
        if not allowed:
            return
        normalized_run_type = (run_type or "").strip()
        if normalized_run_type not in allowed:
            raise ToolAccessDeniedError(
                f"Tool '{tool_name}' is not permitted for run_type '{normalized_run_type or 'unknown'}'."
            )

    def assess_report(
        self,
        *,
        report: Any,
        evidence: dict[str, Any],
        section_keys: list[str],
    ) -> ReportGuardrailResult:
        evidence_items = list(evidence.get("evidence_items") or [])
        evidence_ref_map = {
            str(item.get("evidence_ref")): item
            for item in evidence_items
            if str(item.get("evidence_ref") or "").strip()
        }
        violations: list[dict[str, Any]] = []

        for section_key in section_keys:
            section = getattr(report, section_key)
            title = str(getattr(section, "title", "") or "").strip()
            content = str(getattr(section, "content", "") or "").strip()
            evidence_refs = [str(item).strip() for item in (getattr(section, "evidence_refs", []) or []) if str(item).strip()]
            if not title:
                violations.append(self._violation("missing_section_title", "failed", section=section_key))
            if not content:
                violations.append(self._violation("missing_section_content", "failed", section=section_key))
            unknown_refs = [item for item in evidence_refs if item not in evidence_ref_map]
            if unknown_refs:
                violations.append(
                    self._violation(
                        "unknown_evidence_refs",
                        "failed",
                        section=section_key,
                        refs=unknown_refs,
                    )
                )

        citation_refs: list[str] = []
        for citation in list(getattr(report, "citations", []) or []):
            evidence_ref = str(getattr(citation, "evidence_ref", "") or "").strip()
            citation_refs.append(evidence_ref)
            if evidence_ref and evidence_ref not in evidence_ref_map:
                violations.append(
                    self._violation(
                        "unknown_citation_evidence_ref",
                        "failed",
                        section="citations",
                        refs=[evidence_ref],
                    )
                )

        risk_level = str((evidence.get("case_context") or {}).get("risk_level") or "").strip().lower()
        if risk_level in self.HIGH_RISK_LEVELS:
            for section_key in self.HIGH_RISK_SECTIONS:
                section = getattr(report, section_key)
                evidence_refs = [str(item).strip() for item in (getattr(section, "evidence_refs", []) or []) if str(item).strip()]
                if not evidence_refs:
                    violations.append(
                        self._violation("high_risk_section_requires_evidence", "waiting_review", section=section_key)
                    )
                    continue
                grounded = any(
                    str((evidence_ref_map.get(item) or {}).get("evidence_type") or "") in self.GROUNDING_EVIDENCE_TYPES
                    for item in evidence_refs
                )
                if not grounded:
                    violations.append(
                        self._violation(
                            "high_risk_section_requires_grounding_evidence",
                            "waiting_review",
                            section=section_key,
                            refs=evidence_refs,
                        )
                    )
            if not citation_refs:
                violations.append(self._violation("high_risk_report_requires_citations", "waiting_review"))

        publication_status = "ready"
        if any(item["severity"] == "failed" for item in violations):
            publication_status = "failed"
        elif any(item["severity"] == "waiting_review" for item in violations):
            publication_status = "waiting_review"

        return ReportGuardrailResult(
            publication_status=publication_status,
            violations=violations,
            review_required=publication_status == "waiting_review",
        )

    def _violation(
        self,
        code: str,
        severity: str,
        *,
        section: str | None = None,
        refs: list[str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": code,
            "severity": severity,
        }
        if section:
            payload["section"] = section
        if refs:
            payload["refs"] = refs
        return payload

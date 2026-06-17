from __future__ import annotations

from dataclasses import dataclass
import hmac
from typing import Optional

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass
class ActorContext:
    actor_id: str
    role: str
    auth_mode: str


def _build_actor_context(request: Request) -> ActorContext:
    settings = request.app.state.settings
    actor_id = str(request.headers.get("X-Actor-Id") or "system").strip() or "system"
    role = str(request.headers.get("X-Actor-Role") or settings.default_actor_role or "operator").strip().lower() or "operator"
    auth_mode = "api_key" if settings.auth_enabled else "open"
    return ActorContext(actor_id=actor_id, role=role, auth_mode=auth_mode)


def require_write_api_key(request: Request, api_key: Optional[str] = Security(api_key_header)) -> ActorContext:
    settings = request.app.state.settings
    if not settings.auth_enabled:
        actor = _build_actor_context(request)
        request.state.actor_context = actor
        return actor

    expected_api_key = settings.api_key or ""
    if not expected_api_key:
        raise HTTPException(status_code=503, detail="API key auth is enabled, but WINDPOWER_API_KEY is not configured.")

    if not api_key or not hmac.compare_digest(api_key, expected_api_key):
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")
    actor = _build_actor_context(request)
    request.state.actor_context = actor
    return actor


def get_actor_context(request: Request) -> ActorContext:
    cached = getattr(request.state, "actor_context", None)
    if cached is not None:
        return cached
    actor = _build_actor_context(request)
    request.state.actor_context = actor
    return actor


ROLE_PERMISSIONS = {
    "admin": {"*"},
    "operator": {
        "agent_run:create",
        "agent_run:cancel",
        "agent_run:resume",
        "enhanced_report:generate",
        "evals:run",
        "knowledge:ingest",
        "model_catalog:sync",
    },
    "reviewer": {
        "review:approve",
        "review:reject",
        "review:request_changes",
    },
    "viewer": set(),
}


def require_permissions(*required_perms: str):
    def dependency(
        request: Request,
        actor: ActorContext = Depends(require_write_api_key),
    ) -> ActorContext:
        settings = request.app.state.settings
        if not settings.rbac_enabled:
            return actor

        actor_perms = ROLE_PERMISSIONS.get(actor.role, set())
        if "*" in actor_perms:
            return actor

        for perm in required_perms:
            if perm not in actor_perms:
                raise HTTPException(status_code=403, detail=f"Role '{actor.role}' is missing permission '{perm}'.")
        return actor

    return dependency


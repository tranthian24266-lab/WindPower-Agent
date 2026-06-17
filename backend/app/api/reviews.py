from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.audit_service import AuditService
from app.core.auth import get_actor_context, require_permissions
from app.core.review_service import ReviewService, ReviewServiceError
from app.db.schemas import ReviewDecisionRequest


router = APIRouter(tags=["reviews"])


@router.get("/reviews")
def list_reviews(
    request: Request,
    status: str | None = Query(default=None),
    review_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, object]:
    service = ReviewService(request.app.state.settings)
    tasks = service.list_tasks(status=status, review_type=review_type, limit=limit)
    return {"status": "ok", "count": len(tasks), "tasks": tasks}


@router.get("/reviews/{review_task_id}")
def get_review(request: Request, review_task_id: str) -> dict[str, object]:
    service = ReviewService(request.app.state.settings)
    try:
        task = service.get_task(review_task_id)
    except ReviewServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok", "task": task}


@router.post("/reviews/{review_task_id}/approve", dependencies=[Depends(require_permissions("review:approve"))])
def approve_review(request: Request, review_task_id: str, payload: ReviewDecisionRequest) -> dict[str, object]:
    service = ReviewService(request.app.state.settings)
    actor = get_actor_context(request)
    try:
        task = service.approve(review_task_id, reviewer=payload.reviewer, comment=payload.comment)
    except ReviewServiceError as exc:
        message = str(exc)
        status_code = 404 if "does not exist" in message else 409
        raise HTTPException(status_code=status_code, detail=message) from exc
    AuditService(request.app.state.settings).record(
        actor=actor,
        action="review.approve",
        resource_type="review_task",
        resource_id=review_task_id,
        run_id=task.get("run_id"),
        details={"comment": payload.comment, "reviewer": payload.reviewer},
    )
    return {"status": "ok", "task": task}


@router.post("/reviews/{review_task_id}/reject", dependencies=[Depends(require_permissions("review:reject"))])
def reject_review(request: Request, review_task_id: str, payload: ReviewDecisionRequest) -> dict[str, object]:
    service = ReviewService(request.app.state.settings)
    actor = get_actor_context(request)
    try:
        task = service.reject(review_task_id, reviewer=payload.reviewer, comment=payload.comment)
    except ReviewServiceError as exc:
        message = str(exc)
        status_code = 404 if "does not exist" in message else 409
        raise HTTPException(status_code=status_code, detail=message) from exc
    AuditService(request.app.state.settings).record(
        actor=actor,
        action="review.reject",
        resource_type="review_task",
        resource_id=review_task_id,
        run_id=task.get("run_id"),
        details={"comment": payload.comment, "reviewer": payload.reviewer},
    )
    return {"status": "ok", "task": task}


@router.post("/reviews/{review_task_id}/request-changes", dependencies=[Depends(require_permissions("review:request_changes"))])
def request_changes_review(request: Request, review_task_id: str, payload: ReviewDecisionRequest) -> dict[str, object]:
    service = ReviewService(request.app.state.settings)
    actor = get_actor_context(request)
    try:
        task = service.request_changes(review_task_id, reviewer=payload.reviewer, comment=payload.comment)
    except ReviewServiceError as exc:
        message = str(exc)
        status_code = 404 if "does not exist" in message else 409
        raise HTTPException(status_code=status_code, detail=message) from exc
    AuditService(request.app.state.settings).record(
        actor=actor,
        action="review.request_changes",
        resource_type="review_task",
        resource_id=review_task_id,
        run_id=task.get("run_id"),
        details={"comment": payload.comment, "reviewer": payload.reviewer},
    )
    return {"status": "ok", "task": task}

"""Task submission, retry and user feedback."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from medops.api.contracts import (
    IDEMPOTENCY_KEY_HEADER,
    FeedbackReceipt,
    FeedbackRequest,
    TaskCreateRequest,
    TaskResponse,
)
from medops.api.ports import ApiRuntime
from medops.application.audit import FeedbackService
from medops.application.tasks import TaskService, to_response


def build_router(runtime: ApiRuntime, *, idempotency_ttl_s: int) -> APIRouter:
    router = APIRouter()

    def _tasks(conn: Any) -> TaskService:
        return TaskService(store=runtime.task_store(conn), idempotency_ttl_s=idempotency_ttl_s)

    @router.post("/v1/tasks", response_model=TaskResponse, status_code=202)
    def create_task(body: TaskCreateRequest, request: Request) -> TaskResponse:
        with runtime.connection() as conn:
            user = runtime.authenticator.authenticate(request.headers.get("authorization"), runtime.directory(conn))
            record = _tasks(conn).create(user, body, request.headers.get(IDEMPOTENCY_KEY_HEADER))
        return to_response(record)

    @router.get("/v1/tasks/{task_id}", response_model=TaskResponse)
    def get_task(task_id: str, request: Request) -> TaskResponse:
        with runtime.connection() as conn:
            user = runtime.authenticator.authenticate(request.headers.get("authorization"), runtime.directory(conn))
            record = _tasks(conn).get(user, task_id)
        return to_response(record)

    @router.post("/v1/feedback", response_model=FeedbackReceipt, status_code=201)
    def feedback(body: FeedbackRequest, request: Request) -> FeedbackReceipt:
        with runtime.connection() as conn:
            user = runtime.authenticator.authenticate(request.headers.get("authorization"), runtime.directory(conn))
            service = FeedbackService(store=runtime.trace_store(conn), idempotency_ttl_s=idempotency_ttl_s)
            return service.submit(user, body, request.headers.get(IDEMPOTENCY_KEY_HEADER))

    @router.post("/v1/tasks/{task_id}/retry", response_model=TaskResponse, status_code=202)
    def retry_task(task_id: str, request: Request) -> TaskResponse:
        with runtime.connection() as conn:
            user = runtime.authenticator.authenticate(request.headers.get("authorization"), runtime.directory(conn))
            record = _tasks(conn).retry(user, task_id)
        return to_response(record)

    return router

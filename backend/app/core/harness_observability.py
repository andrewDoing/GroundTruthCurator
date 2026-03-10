from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request

from .config import REPO_ROOT, settings

HARNESS_DIR = REPO_ROOT.parent / ".harness"
LOG_PATH = HARNESS_DIR / "logs.jsonl"
TRACE_PATH = HARNESS_DIR / "traces.jsonl"


def _append_jsonl(path: Path, entry: dict[str, object | None]) -> None:
    HARNESS_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _level_for_status(status_code: int) -> str:
    if status_code >= 500:
        return "ERROR"
    if status_code >= 400:
        return "WARN"
    return "INFO"


def _status_for_status(status_code: int) -> str:
    return "error" if status_code >= 400 else "ok"


def install_harness_jsonl_middleware(app: FastAPI) -> FastAPI:
    @app.middleware("http")
    async def _write_harness_events(request: Request, call_next):  # type: ignore[no-redef]
        started_at = _utc_now()
        started_perf = perf_counter()
        trace_id = uuid4().hex
        span_id = uuid4().hex[:16]
        request_name = f"{request.method} {request.url.path}"

        try:
            response = await call_next(request)
        except Exception as exc:
            ended_at = _utc_now()
            duration_ms = round((perf_counter() - started_perf) * 1000)
            status_code = 500

            _append_jsonl(
                LOG_PATH,
                {
                    "ts": ended_at.isoformat(),
                    "level": "ERROR",
                    "msg": f"{request_name} 500",
                    "service": settings.SERVICE_NAME,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "duration_ms": duration_ms,
                    "status": "error",
                    "method": request.method,
                    "path": request.url.path,
                    "http_status": status_code,
                    "error": exc.__class__.__name__,
                },
            )
            _append_jsonl(
                TRACE_PATH,
                {
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_id": None,
                    "name": request_name,
                    "service": settings.SERVICE_NAME,
                    "start": started_at.isoformat(),
                    "end": ended_at.isoformat(),
                    "duration_ms": duration_ms,
                    "status": "error",
                    "method": request.method,
                    "path": request.url.path,
                    "http_status": status_code,
                },
            )
            raise

        ended_at = _utc_now()
        duration_ms = round((perf_counter() - started_perf) * 1000)
        level = _level_for_status(response.status_code)
        status = _status_for_status(response.status_code)
        error = "client error" if response.status_code >= 400 else None
        if response.status_code >= 500:
            error = "server error"

        _append_jsonl(
            LOG_PATH,
            {
                "ts": ended_at.isoformat(),
                "level": level,
                "msg": f"{request_name} {response.status_code}",
                "service": settings.SERVICE_NAME,
                "trace_id": trace_id,
                "span_id": span_id,
                "duration_ms": duration_ms,
                "status": status,
                "method": request.method,
                "path": request.url.path,
                "http_status": response.status_code,
                "error": error,
            },
        )
        _append_jsonl(
            TRACE_PATH,
            {
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_id": None,
                "name": request_name,
                "service": settings.SERVICE_NAME,
                "start": started_at.isoformat(),
                "end": ended_at.isoformat(),
                "duration_ms": duration_ms,
                "status": status,
                "method": request.method,
                "path": request.url.path,
                "http_status": response.status_code,
            },
        )
        return response

    return app

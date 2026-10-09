"""
Ingestion Service - Minh.

Nhan structured log tu demo-app, validate theo docs/architect/contracts/log-schema.json,
ghi vao kho du lieu (hoac quarantine neu sai schema).

Chay thu:
    pip install -r ingestion/requirements.txt
    docker compose -f ingestion/docker-compose.yml up -d   # OpenSearch cuc bo
    uvicorn ingestion.src.main:app --reload --port 8000

Khong co Docker? Dung backend nhe khong persist:
    LOG_STORE_BACKEND=memory uvicorn ingestion.src.main:app --reload --port 8000
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .retention import run_retention
from .storage import LogStore, get_store
from .validator import validate_log

store: LogStore = get_store()

_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lap lich chay retention job dinh ky (xem retention.py). Khoang cach
    cau hinh qua RETENTION_INTERVAL_HOURS (mac dinh 24h, env, khong hardcode).
    Dat 0 hoac am de tat (vd. khi retention duoc chay rieng qua OS cron bang
    `ingestion/scripts/run_retention.py` thay vi scheduler trong tien trinh nay).
    """
    global _scheduler
    interval_hours = float(os.environ.get("RETENTION_INTERVAL_HOURS", "24"))

    if os.environ.get("RETENTION_RUN_ON_STARTUP", "false").strip().lower() == "true":
        run_retention(store)

    if interval_hours > 0:
        from apscheduler.schedulers.background import BackgroundScheduler

        _scheduler = BackgroundScheduler()
        _scheduler.add_job(
            run_retention,
            "interval",
            hours=interval_hours,
            args=[store],
            id="retention_job",
            replace_existing=True,
        )
        _scheduler.start()

    yield

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)


app = FastAPI(title="Log Anomaly Explorer - Ingestion Service", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ingestion"}


@app.post("/ingest", status_code=202)
def ingest(payload: dict):
    errors = validate_log(payload)
    if errors:
        store.write_quarantine(payload, errors)
        # Hop dong (docs/architect/contracts/api-contract.md): log sai schema
        # phai tra ve 400, KHONG chen vao index chinh.
        return JSONResponse(
            status_code=400,
            content={"accepted": False, "reason": "schema_validation_failed", "details": errors},
        )

    log_id = str(uuid.uuid4())
    store.write_log(log_id, payload)
    return {"accepted": True, "log_id": log_id}


@app.get("/search")
def search(
    service: str | None = None,
    trace_id: str | None = None,
    q: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
):
    """Expose tam thoi de Nghia test ngay; query-api that se goi thang vao
    `get_store()` (xem storage.py) thay vi qua HTTP nay."""
    results = store.search(service=service, trace_id=trace_id, query=q, time_from=time_from, time_to=time_to)
    return {"total": len(results), "results": results}

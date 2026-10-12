"""
Demo App - nguon log cho Log Anomaly Explorer.

Phu trach: Manh.
Trach nhiem: sinh structured log + trace (qua OpenTelemetry), va cung cap co che
fault injection co chu dich de tao du lieu cho labeled incidents (Nam).

Chay thu:
    pip install -r demo-app/requirements.txt
    uvicorn demo-app.src.main:app --reload --port 8001
"""

from __future__ import annotations

import os
import random
import time
import traceback
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException, Request

from .telemetry import get_current_trace_context, get_tracer, setup_telemetry

SERVICE_NAME = "demo-web"
MOBILE_SERVICE_NAME = "demo-mobile-api"
INGESTION_URL = os.environ.get("INGESTION_URL", "http://localhost:8000/ingest")

app = FastAPI(title="Log Anomaly Explorer - Demo App")

setup_telemetry(SERVICE_NAME)
_tracer = get_tracer(__name__)


@app.middleware("http")
async def tracing_middleware(request: Request, call_next):
    """Mo mot span OTel cho moi request, de get_current_trace_context() trong
    emit_log() luon co trace_id/span_id thuc khi xu ly request."""
    with _tracer.start_as_current_span(f"{request.method} {request.url.path}") as span:
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.route", request.url.path)
        response = await call_next(request)
        span.set_attribute("http.status_code", response.status_code)
        return response


def _resolve_service_name(request: Request) -> str:
    """Luong mobile duoc gia lap qua header X-Client: mobile tren cung endpoint
    (xem demo-app/README.md), thay vi dung rieng mot endpoint khac."""
    if request.headers.get("x-client", "").lower() == "mobile":
        return MOBILE_SERVICE_NAME
    return SERVICE_NAME


def emit_log(
    level: str,
    message: str,
    stack_trace: str | None = None,
    service: str | None = None,
) -> None:
    """Sinh mot structured log dung theo docs/architect/contracts/log-schema.json
    va gui ve Ingestion, kem trace_id/span_id thuc tu OpenTelemetry."""
    trace_ctx = get_current_trace_context()

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "service": service or SERVICE_NAME,
        "trace_id": trace_ctx["trace_id"],
        "span_id": trace_ctx["span_id"],
        "message": message,
        "stack_trace": stack_trace,
    }
    try:
        httpx.post(INGESTION_URL, json=payload, timeout=2.0)
    except httpx.HTTPError:
        # Khong de loi gui log lam sap ung dung demo.
        pass


def _emit_malformed_log(service: str) -> None:
    """Fault injection loai 'bad_schema': gui THANG mot log SAI
    docs/architect/contracts/log-schema.json ve Ingestion (bo qua emit_log()
    vi emit_log luon sinh payload hop le), de kiem tra co che quarantine
    cua Ingestion (Minh) khi nhan du lieu khong dung hop dong."""
    malformed_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "CRITICAL",  # khong nam trong enum hop le cua log-schema.json
        "service": service,
        # thieu truong bat buoc "trace_id" va "span_id" mot cach co chu dich
        "message": "Simulated malformed log (invalid level, missing trace/span id)",
    }
    try:
        httpx.post(INGESTION_URL, json=malformed_payload, timeout=2.0)
    except httpx.HTTPError:
        pass


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/api/items")
def list_items(request: Request) -> dict:
    """Endpoint happy-path binh thuong, dung de tao log nen (baseline).

    Goi kem header `X-Client: mobile` de gia lap luong mobile (log duoc
    gan service=demo-mobile-api thay vi demo-web)."""
    service = _resolve_service_name(request)
    emit_log("INFO", "Listed items successfully", service=service)
    return {"items": ["item-1", "item-2", "item-3"], "service": service}


@app.get("/simulate-error")
def simulate_error(request: Request, rate: float = 0.3, fault_type: str = "error") -> dict:
    """Fault injection co chu dich.

    Goi endpoint nay lap lai (vd. bang demo-app/scripts/trigger_fault_window.py
    hoac load-tests/locustfile.py) voi `rate` khac nhau de tao ra cac giai doan
    bat thuong co kiem soat, phuc vu:
      - GitHub evidence "fault injection"
      - Du lieu dau vao cho "labeled incidents" (Nam tu gan nhan
        giai doan nay la mot incident that trong qua trinh danh gia precision/recall)

    `fault_type`:
      - "error" (mac dinh): loi 500 ngau nhien o tang ung dung
        (RuntimeError: Simulated downstream failure).
      - "timeout": gia lap downstream cham, tra ve 504 sau khi delay.
      - "bad_schema": gui thang mot log SAI log-schema.json ve Ingestion
        (thieu truong bat buoc, sai enum `level`) de kiem tra co che
        quarantine cua Ingestion.
      - "not_found": loi nghiep vu 404 (ValueError: User <id> not found),
        id ngau nhien moi lan - signature khac han "error", dong thoi
        chung minh clustering.normalize_message() chuan hoa dung cac loi
        cung "hinh dang" nhung khac gia tri so (xem clustering/src/clustering.py).
      - "db_error": loi ha tang 503 (ConnectionError: Database connection
        pool exhausted) - mo phong loi tang ket noi CSDL, khac han ca
        "error" (tang ung dung) lan "not_found" (tang nghiep vu) ve stack
        trace/signature, de co nhieu hon 1 loai cum that trong he thong
        thay vi chi 1 loai lap lai o nhieu service.
    """
    service = _resolve_service_name(request)

    if random.random() >= rate:
        emit_log(
            "INFO",
            f"simulate-error call succeeded (no fault injected, fault_type={fault_type})",
            service=service,
        )
        return {"status": "ok", "rate": rate, "fault_type": fault_type}

    if fault_type == "timeout":
        delay_s = round(random.uniform(3.0, 6.0), 2)
        emit_log("WARN", f"Simulated slow downstream call ({delay_s}s)", service=service)
        time.sleep(delay_s)
        raise HTTPException(status_code=504, detail=f"Simulated timeout after {delay_s}s")

    if fault_type == "bad_schema":
        _emit_malformed_log(service)
        raise HTTPException(status_code=502, detail="Simulated malformed log emitted to ingestion")

    if fault_type == "not_found":
        user_id = random.randint(1000, 9999)
        try:
            raise ValueError(f"User {user_id} not found")
        except ValueError:
            emit_log(
                "ERROR",
                f"User {user_id} not found",
                stack_trace=traceback.format_exc(),
                service=service,
            )
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    if fault_type == "db_error":
        try:
            raise ConnectionError("Database connection pool exhausted")
        except ConnectionError:
            emit_log(
                "ERROR",
                "Database connection pool exhausted",
                stack_trace=traceback.format_exc(),
                service=service,
            )
            raise HTTPException(status_code=503, detail="Database connection pool exhausted")

    if fault_type != "error":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown fault_type '{fault_type}'. "
                "Dung: error | timeout | bad_schema | not_found | db_error"
            ),
        )

    try:
        raise RuntimeError("Simulated downstream failure")
    except RuntimeError:
        emit_log(
            "ERROR",
            "Simulated downstream failure",
            stack_trace=traceback.format_exc(),
            service=service,
        )
        raise HTTPException(status_code=500, detail="Simulated downstream failure")

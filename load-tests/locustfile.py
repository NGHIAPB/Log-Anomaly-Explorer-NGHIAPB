"""
Load test cho Log Anomaly Explorer, dung Locust.

Chay thu:
    pip install locust
    locust -f locustfile.py --host http://localhost:8000

So nguoi dung dong thoi (concurrency) cau hinh khi chay Locust (--users),
KHONG hardcode trong file nay - moi lan test co the dung muc tai khac nhau
tuy muc tieu (vd. theo yeu cau cua bien the ca nhan dang lam).

TODO (Nghia): bo sung task goi /search, /clusters, /clusters/{id} cho load test end-to-end.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

from locust import HttpUser, between, task

_SERVICES = ["demo-web", "demo-mobile-api"]
_MESSAGES_BY_LEVEL = {
    "INFO": ["Listed items successfully", "Request completed", "Cache hit for key"],
    "WARN": ["Simulated slow downstream call", "Retrying downstream call"],
    "ERROR": ["Simulated downstream failure", "User not found", "Upstream timeout"],
}
# Trong so phong theo ty le level thuc te tu demo-app (Manh): da so la INFO,
# mot phan nho ERROR/WARN tao ra tu /simulate-error.
_LEVEL_WEIGHTS = [("INFO", 7), ("WARN", 1), ("ERROR", 2)]


def _random_level() -> str:
    levels, weights = zip(*_LEVEL_WEIGHTS)
    return random.choices(levels, weights=weights, k=1)[0]


def _valid_log_payload() -> dict:
    """Payload hop le theo docs/architect/contracts/log-schema.json, mo phong
    du lieu thuc demo-app (Manh) gui ve /ingest (bao gom ca field tuy chon
    stack_trace/metadata de test duong ghi day du, khong chi happy path)."""
    level = _random_level()
    message = random.choice(_MESSAGES_BY_LEVEL[level])
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "service": random.choice(_SERVICES),
        "trace_id": uuid.uuid4().hex,
        "span_id": uuid.uuid4().hex[:16],
        "message": message,
        "metadata": {"http.status_code": 500 if level == "ERROR" else 200},
    }
    if level in ("ERROR", "WARN"):
        payload["stack_trace"] = f"Traceback (most recent call last):\n  ...\n{message}"
    return payload


def _malformed_log_payload() -> dict:
    """Payload SAI log-schema.json (thieu truong bat buoc) - mo phong fault
    injection `bad_schema` cua Manh, de do throughput/ty le loi cua duong
    quarantine duoi tai (khong chi duong happy path)."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "CRITICAL",  # khong nam trong enum hop le
        "service": random.choice(_SERVICES),
        "message": "Load test malformed log entry",
    }


class IngestionUser(HttpUser):
    """Mo phong demo-app lien tuc gui log ve Ingestion Service."""

    wait_time = between(0.1, 0.5)
    host = "http://localhost:8000"

    @task(9)
    def ingest_valid_log(self):
        self.client.post("/ingest", json=_valid_log_payload())

    @task(1)
    def ingest_malformed_log(self):
        """~10% log sai schema, de danh gia duong quarantine (expect HTTP 400,
        xem docs/architect/contracts/api-contract.md) khong lam sap service
        khi tai tang."""
        with self.client.post(
            "/ingest", json=_malformed_log_payload(), catch_response=True
        ) as resp:
            if resp.status_code == 400:
                resp.success()
            else:
                resp.failure(f"expected 400 for malformed log, got {resp.status_code}")


class QueryUser(HttpUser):
    """Mo phong nguoi dung / doi tac goi Query & Incident API."""

    wait_time = between(0.5, 2.0)
    host = "http://localhost:8002"

    @task
    def list_clusters(self):
        self.client.get("/clusters")

"""
Query & Incident API - Nghia.

Search log + Incident View (chi tiet cum + lien ket trace/request).
Dung chung storage cua Ingestion (Minh) va cluster data cua
Clustering (Nam) - xem docs/architect/contracts/api-contract.md.

Chay thu (voi du lieu that, can OpenSearch dang chay - xem
ingestion/docker-compose.yml va ingestion/README.md):
    pip install -r query-api/requirements.txt
    uvicorn query-api.src.main:app --reload --port 8002

Khong co Docker? Dung backend nhe khong persist (phai dong bo voi
ingestion/clustering, xem query-api/README.md):
    LOG_STORE_BACKEND=memory CLUSTER_STORE_BACKEND=memory \
    uvicorn query-api.src.main:app --reload --port 8002
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from clustering.src.storage import get_cluster_store
from ingestion.src.storage import get_store

app = FastAPI(title="Log Anomaly Explorer - Query & Incident API")

# API chi doc (GET), khong co auth o MVP nay - mo CORS de client trinh duyet
# (dashboard rieng, Swagger UI tu domain khac, ...) goi truc tiep duoc khi da
# deploy len web (xem docs/task/deployment.md).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_DEFAULT_SEARCH_WINDOW_HOURS = 24
# api-contract.md - GET /clusters: "since mac dinh theo retention hien hanh".
# Dung chung RETENTION_DAYS voi ingestion (xem ingestion/src/retention.py) vi
# do la chinh sach retention thuc te dang ap dung cho log lam nen cho cluster.
_RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "30"))

log_store = get_store()
cluster_store = get_cluster_store()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "query-api"}


@app.get("/search")
def search(
    service: str | None = None,
    trace_id: str | None = None,
    q: str | None = None,
    time_from: str | None = Query(default=None, alias="from"),
    time_to: str | None = Query(default=None, alias="to"),
):
    """Tim log tho theo field (khong phai semantic/vector search), xem
    api-contract.md muc "GET /search". Mac dinh 24h gan nhat neu khong
    truyen `from`."""
    if not time_from:
        time_from = (datetime.now(timezone.utc) - timedelta(hours=_DEFAULT_SEARCH_WINDOW_HOURS)).isoformat()

    results = log_store.search(
        service=service,
        trace_id=trace_id,
        query=q,
        time_from=time_from,
        time_to=time_to,
    )
    return {"total": len(results), "results": results}


@app.get("/clusters")
def list_clusters(
    status: str | None = None,
    since: str | None = None,
):
    """Danh sach cum bat thuong, doc tu ClusterRecord thuc cua Nam. Xem
    api-contract.md muc "GET /clusters". Mac dinh `since` theo retention
    hien hanh (RETENTION_DAYS) neu khong truyen."""
    if not since:
        since = (datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)).isoformat()
    clusters = cluster_store.list_clusters(status=status, since=since)
    return {"total": len(clusters), "clusters": clusters}


@app.get("/clusters/{cluster_id}")
def get_cluster(cluster_id: str):
    """Chi tiet mot cum - Incident View. Dien day du `logs` bang cach tra
    `log_ids` cua ClusterRecord ve LogStore thuc cua Minh, xem
    api-contract.md muc "GET /clusters/{cluster_id}"."""
    cluster = cluster_store.get_cluster(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="cluster not found")

    logs = log_store.get_by_ids(cluster.get("log_ids", []))
    return {**cluster, "logs": logs}

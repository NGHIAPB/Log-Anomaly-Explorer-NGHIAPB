"""Test cho query-api/src/main.py (FastAPI) - dung backend memory (khong can
OpenSearch that) qua TestClient.

`log_store`/`cluster_store` trong main.py la singleton duoc tao 1 LAN luc
import module (xem ingestion/src/storage.get_store() va
clustering/src/storage.get_cluster_store()), nen phai set bien moi truong
LOG_STORE_BACKEND/CLUSTER_STORE_BACKEND = "memory" TRUOC khi import, va
import qua importlib (ten module "query-api.src.main" co dau "-" khong
dung duoc voi cu phap "import" thong thuong)."""

from __future__ import annotations

import importlib
import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

os.environ["LOG_STORE_BACKEND"] = "memory"
os.environ["CLUSTER_STORE_BACKEND"] = "memory"

_main = importlib.import_module("query-api.src.main")
client = TestClient(_main.app)

# Thoi diem TUONG DOI, khong hardcode ngay cu the: /search mac dinh chi tra
# 24h gan nhat va /clusters mac dinh theo RETENTION_DAYS, nen log/cluster gan
# ngay co dinh se tu roi ra ngoai cua so mac dinh khi thoi gian troi qua
# (da gap that: test viet ngay 2026-10-12 bat dau do ngay 2026-10-22).
_NOW = datetime.now(timezone.utc).isoformat()


@pytest.fixture(autouse=True)
def _reset_stores():
    """Singleton dung chung process nen phai don giua cac test de tranh
    log/cluster cua test truoc lam sai ket qua test sau."""
    _main.log_store._logs.clear()
    _main.cluster_store._clusters.clear()
    yield


def _write_log(log_id: str, **fields) -> None:
    base = {"timestamp": _NOW, "service": "demo-web", "message": "x"}
    base.update(fields)
    _main.log_store.write_log(log_id, base)


def _write_cluster(cluster_id: str, **fields) -> None:
    base = {
        "cluster_id": cluster_id,
        "score": 1.0,
        "log_ids": [],
        "first_seen": _NOW,
        "last_seen": _NOW,
        "status": "normal",
    }
    base.update(fields)
    _main.cluster_store.write_cluster(base)


class TestHealth:
    def test_health_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "service": "query-api"}


class TestSearch:
    def test_khong_filter_tra_ve_tat_ca(self):
        _write_log("1")
        _write_log("2")
        resp = client.get("/search")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2

    def test_filter_theo_service(self):
        _write_log("1", service="demo-web")
        _write_log("2", service="demo-mobile-api")
        resp = client.get("/search", params={"service": "demo-mobile-api"})
        body = resp.json()
        assert body["total"] == 1
        assert body["results"][0]["log_id"] == "2"

    def test_filter_theo_q_dung_alias_tu_khoa(self):
        _write_log("1", message="Simulated downstream failure")
        _write_log("2", message="Listed items successfully")
        resp = client.get("/search", params={"q": "simulated"})
        body = resp.json()
        assert body["total"] == 1
        assert body["results"][0]["log_id"] == "1"

    def test_filter_theo_from_to_alias(self):
        _write_log("old", timestamp="2026-09-01T00:00:00Z")
        _write_log("new", timestamp="2026-10-12T09:00:00Z")
        resp = client.get("/search", params={"from": "2026-10-01T00:00:00Z", "to": "2026-10-13T00:00:00Z"})
        body = resp.json()
        assert body["total"] == 1
        assert body["results"][0]["log_id"] == "new"

    def test_khong_truyen_from_mac_dinh_24h_gan_nhat(self):
        _write_log("cu", timestamp="2020-01-01T00:00:00Z")
        _write_log("moi", timestamp=_NOW)
        resp = client.get("/search")
        body = resp.json()
        assert body["total"] == 1
        assert body["results"][0]["log_id"] == "moi"


class TestListClusters:
    def test_khong_filter_tra_ve_tat_ca(self):
        _write_cluster("c1")
        _write_cluster("c2")
        resp = client.get("/clusters")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_filter_theo_status(self):
        _write_cluster("c1", status="normal")
        _write_cluster("c2", status="alerted")
        resp = client.get("/clusters", params={"status": "alerted"})
        body = resp.json()
        assert body["total"] == 1
        assert body["clusters"][0]["cluster_id"] == "c2"

    def test_khong_truyen_since_mac_dinh_theo_retention(self):
        _write_cluster("cu", last_seen="2020-01-01T00:00:00Z")
        _write_cluster("moi", last_seen=_NOW)
        resp = client.get("/clusters")
        body = resp.json()
        assert body["total"] == 1
        assert body["clusters"][0]["cluster_id"] == "moi"


class TestGetCluster:
    def test_cluster_khong_ton_tai_404(self):
        resp = client.get("/clusters/khong-ton-tai")
        assert resp.status_code == 404

    def test_cluster_ton_tai_dien_day_du_logs_tu_log_ids(self):
        _write_log("log-1", message="Simulated downstream failure")
        _write_log("log-2", message="Simulated downstream failure")
        _write_cluster("c1", log_ids=["log-1", "log-2"])

        resp = client.get("/clusters/c1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cluster_id"] == "c1"
        assert {l["log_id"] for l in body["logs"]} == {"log-1", "log-2"}

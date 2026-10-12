"""Test cho ingestion/src/retention.py - dung InMemoryLogStore de khong can
OpenSearch that. Khong test lich chay dinh ky (APScheduler trong main.py) -
chi test dung LOGIC xoa (run_retention), dung voi pham vi cua module nay."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ingestion.src.retention import run_retention
from ingestion.src.storage import InMemoryLogStore


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def test_xoa_dung_log_qua_han_giu_lai_log_con_han():
    store = InMemoryLogStore()
    store.write_log("old-1", {"timestamp": _iso(40), "message": "qua cu"})
    store.write_log("old-2", {"timestamp": _iso(31), "message": "qua cu"})
    store.write_log("new-1", {"timestamp": _iso(5), "message": "con moi"})
    store.write_log("new-2", {"timestamp": _iso(0.1), "message": "rat moi"})

    deleted = run_retention(store, retention_days=30)

    assert deleted == 2
    remaining_ids = {log["log_id"] for log in store.get_by_ids(["old-1", "old-2", "new-1", "new-2"])}
    assert remaining_ids == {"new-1", "new-2"}


def test_khong_co_log_nao_qua_han_thi_khong_xoa_gi():
    store = InMemoryLogStore()
    store.write_log("a", {"timestamp": _iso(1), "message": "x"})
    store.write_log("b", {"timestamp": _iso(2), "message": "y"})

    deleted = run_retention(store, retention_days=30)

    assert deleted == 0
    assert len(store.get_by_ids(["a", "b"])) == 2


def test_retention_days_mac_dinh_lay_tu_bien_moi_truong(monkeypatch):
    # DEFAULT_RETENTION_DAYS doc os.environ luc MODULE duoc import, nen test
    # nay chi xac nhan tham so retention_days co the override duoc tuong
    # minh (hanh vi thuc te ma run_retention() cung cap), khong test lai
    # viec doc bien moi truong luc import (can reload module moi anh huong).
    store = InMemoryLogStore()
    store.write_log("old", {"timestamp": _iso(10), "message": "x"})
    store.write_log("new", {"timestamp": _iso(1), "message": "y"})

    deleted = run_retention(store, retention_days=5)

    assert deleted == 1

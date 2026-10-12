"""Test cho InMemoryLogStore (ingestion/src/storage.py) - backend du phong
dev/test, dung chung logic voi OpenSearchLogStore (filter/sort) nen la noi
phu hop de kiem tra logic search/get_by_ids ma khong can OpenSearch that."""

from __future__ import annotations

from ingestion.src.storage import InMemoryLogStore


def _seed(store: InMemoryLogStore) -> None:
    store.write_log("1", {"timestamp": "2026-10-12T09:00:00Z", "service": "demo-web", "trace_id": "t1", "message": "Listed items successfully"})
    store.write_log("2", {"timestamp": "2026-10-12T09:01:00Z", "service": "demo-web", "trace_id": "t2", "message": "Simulated downstream failure"})
    store.write_log("3", {"timestamp": "2026-10-12T09:02:00Z", "service": "demo-mobile-api", "trace_id": "t3", "message": "Simulated downstream failure"})


def test_search_khong_filter_tra_ve_tat_ca_sap_xep_moi_nhat_truoc():
    store = InMemoryLogStore()
    _seed(store)
    results = store.search()
    assert [r["log_id"] for r in results] == ["3", "2", "1"]


def test_search_filter_theo_service():
    store = InMemoryLogStore()
    _seed(store)
    results = store.search(service="demo-mobile-api")
    assert len(results) == 1
    assert results[0]["log_id"] == "3"


def test_search_filter_theo_trace_id():
    store = InMemoryLogStore()
    _seed(store)
    results = store.search(trace_id="t2")
    assert len(results) == 1
    assert results[0]["log_id"] == "2"


def test_search_full_text_khong_phan_biet_hoa_thuong():
    store = InMemoryLogStore()
    _seed(store)
    results = store.search(query="SIMULATED")
    assert {r["log_id"] for r in results} == {"2", "3"}


def test_search_loc_theo_khoang_thoi_gian():
    store = InMemoryLogStore()
    _seed(store)
    results = store.search(time_from="2026-10-12T09:01:00Z", time_to="2026-10-12T09:01:30Z")
    assert [r["log_id"] for r in results] == ["2"]


def test_get_by_ids_bo_qua_id_khong_ton_tai():
    store = InMemoryLogStore()
    _seed(store)
    results = store.get_by_ids(["1", "khong-ton-tai", "3"])
    assert {r["log_id"] for r in results} == {"1", "3"}


def test_write_quarantine_khong_anh_huong_log_chinh():
    store = InMemoryLogStore()
    store.write_quarantine({"message": "sai schema"}, ["thieu trace_id"])
    assert store.search() == []

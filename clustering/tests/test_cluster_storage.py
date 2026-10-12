"""Test cho InMemoryClusterStore (clustering/src/storage.py) - bao gom ca
to_cluster_record() (validate + strip truong noi bo) va _merge_cluster()
(upsert cluster theo cluster_id qua nhieu lan tinh)."""

from __future__ import annotations

import pytest

from clustering.src.storage import InMemoryClusterStore, to_cluster_record


def _record(cluster_id: str = "c1", score: float = 1.0, status: str = "normal", **overrides) -> dict:
    base = {
        "cluster_id": cluster_id,
        "signature": "simulated downstream failure",
        "score": score,
        "log_ids": ["1", "2"],
        "trace_ids": ["t1", "t2"],
        "first_seen": "2026-10-12T09:00:00Z",
        "last_seen": "2026-10-12T09:01:00Z",
        "status": status,
        "service": "demo-web",  # truong noi bo, khong trong schema
    }
    base.update(overrides)
    return base


class TestToClusterRecord:
    def test_loai_bo_truong_noi_bo_service(self):
        doc = to_cluster_record(_record())
        assert "service" not in doc
        assert doc["cluster_id"] == "c1"

    def test_thieu_truong_bat_buoc_raise_valueerror(self):
        # "cluster_id" nam trong "required" cua schema (khac "signature" -
        # tuy co trong properties nhung KHONG bat buoc, xem cluster-record.schema.json).
        bad = _record()
        del bad["cluster_id"]
        with pytest.raises(ValueError):
            to_cluster_record(bad)


class TestInMemoryClusterStore:
    def test_write_va_get_cluster(self):
        store = InMemoryClusterStore()
        store.write_cluster(_record())
        result = store.get_cluster("c1")
        assert result is not None
        assert result["score"] == 1.0

    def test_get_cluster_khong_ton_tai_tra_ve_none(self):
        store = InMemoryClusterStore()
        assert store.get_cluster("khong-ton-tai") is None

    def test_write_lai_cung_cluster_id_gop_log_ids_va_lay_status_moi_nhat(self):
        store = InMemoryClusterStore()
        store.write_cluster(_record(status="normal", score=1.0, log_ids=["1"], trace_ids=["t1"],
                                      first_seen="2026-10-12T09:00:00Z", last_seen="2026-10-12T09:01:00Z"))
        store.write_cluster(_record(status="alerted", score=5.0, log_ids=["2"], trace_ids=["t2"],
                                      first_seen="2026-10-12T09:05:00Z", last_seen="2026-10-12T09:06:00Z"))

        merged = store.get_cluster("c1")
        assert merged["status"] == "alerted"  # lay theo lan tinh gan nhat
        assert merged["score"] == 5.0
        assert set(merged["log_ids"]) == {"1", "2"}  # gop lai
        assert merged["first_seen"] == "2026-10-12T09:00:00Z"  # giu som nhat
        assert merged["last_seen"] == "2026-10-12T09:06:00Z"  # giu muon nhat

    def test_list_clusters_filter_theo_status(self):
        store = InMemoryClusterStore()
        store.write_cluster(_record(cluster_id="c1", status="normal"))
        store.write_cluster(_record(cluster_id="c2", status="alerted"))
        results = store.list_clusters(status="alerted")
        assert [c["cluster_id"] for c in results] == ["c2"]

    def test_list_clusters_sap_xep_theo_last_seen_moi_nhat_truoc(self):
        store = InMemoryClusterStore()
        store.write_cluster(_record(cluster_id="c1", last_seen="2026-10-12T09:00:00Z"))
        store.write_cluster(_record(cluster_id="c2", last_seen="2026-10-12T10:00:00Z"))
        results = store.list_clusters()
        assert [c["cluster_id"] for c in results] == ["c2", "c1"]

    def test_list_clusters_filter_theo_since(self):
        store = InMemoryClusterStore()
        store.write_cluster(_record(cluster_id="c1", last_seen="2026-10-12T08:00:00Z"))
        store.write_cluster(_record(cluster_id="c2", last_seen="2026-10-12T10:00:00Z"))
        results = store.list_clusters(since="2026-10-12T09:00:00Z")
        assert [c["cluster_id"] for c in results] == ["c2"]

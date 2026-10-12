"""Test cho clustering/evaluation/precision_recall.py - do GitHub evidence
"precision/recall" dua vao module nay, can bao ve de so lieu bao cao dang tin cay."""

from __future__ import annotations

import json

from clustering.evaluation.precision_recall import (
    _cluster_overlaps_incident,
    _windows_overlap,
    _with_service,
    evaluate,
)


def _write_incidents(tmp_path, incidents: list[dict]):
    path = tmp_path / "labeled_incidents.json"
    path.write_text(json.dumps({"incidents": incidents}), encoding="utf-8")
    return path


def _incident(incident_id="i1", service="demo-web", signature="simulated downstream failure",
              window_from="2026-10-12T09:00:00Z", window_to="2026-10-12T09:10:00Z") -> dict:
    return {
        "incident_id": incident_id,
        "service": service,
        "expected_cluster_signature": signature,
        "window_from": window_from,
        "window_to": window_to,
    }


def _cluster(service="demo-web", signature="simulated downstream failure",
             first_seen="2026-10-12T09:02:00Z", last_seen="2026-10-12T09:05:00Z") -> dict:
    return {"service": service, "signature": signature, "first_seen": first_seen, "last_seen": last_seen}


class TestWindowsOverlap:
    def test_chong_lap_dung_dinh_dang_iso(self):
        assert _windows_overlap(
            "2026-10-12T09:00:00Z", "2026-10-12T09:10:00Z",
            "2026-10-12T09:05:00Z", "2026-10-12T09:20:00Z",
        ) is True

    def test_khong_chong_lap(self):
        assert _windows_overlap(
            "2026-10-12T09:00:00Z", "2026-10-12T09:10:00Z",
            "2026-10-12T10:00:00Z", "2026-10-12T10:10:00Z",
        ) is False

    def test_mot_khung_nam_tron_trong_khung_kia(self):
        assert _windows_overlap(
            "2026-10-12T09:00:00Z", "2026-10-12T10:00:00Z",
            "2026-10-12T09:20:00Z", "2026-10-12T09:30:00Z",
        ) is True


class TestClusterOverlapsIncident:
    def test_khop_ca_service_signature_va_thoi_gian(self):
        assert _cluster_overlaps_incident(_cluster(), _incident()) is True

    def test_khac_signature_khong_khop(self):
        cluster = _cluster(signature="loi khac")
        assert _cluster_overlaps_incident(cluster, _incident()) is False

    def test_khac_service_khong_khop_du_cung_signature(self):
        """Day la ly do _cluster_overlaps_incident phai so ca service, khong
        chi signature - tranh tinh nham false positive giua 2 service khac nhau
        gay ra loi cung ten (xem docstring ham nay va fix group_similar_errors)."""
        cluster = _cluster(service="demo-mobile-api")
        assert _cluster_overlaps_incident(cluster, _incident()) is False

    def test_khong_chong_lap_thoi_gian_khong_khop(self):
        cluster = _cluster(first_seen="2026-10-12T12:00:00Z", last_seen="2026-10-12T12:05:00Z")
        assert _cluster_overlaps_incident(cluster, _incident()) is False


class TestEvaluate:
    def test_khong_co_cluster_predicted_precision_0(self, tmp_path):
        path = _write_incidents(tmp_path, [_incident()])
        result = evaluate([], labeled_path=path)
        assert result["precision"] == 0.0
        assert result["recall"] == 0.0
        assert result["false_negative"] == 1

    def test_khong_co_incident_nao_recall_0(self, tmp_path):
        path = _write_incidents(tmp_path, [])
        result = evaluate([_cluster()], labeled_path=path)
        assert result["recall"] == 0.0
        assert result["precision"] == 0.0  # khong incident nao de khop -> false positive

    def test_1_cluster_khop_dung_1_incident_precision_recall_1(self, tmp_path):
        path = _write_incidents(tmp_path, [_incident()])
        result = evaluate([_cluster()], labeled_path=path)
        assert result == {
            "precision": 1.0, "recall": 1.0,
            "true_positive": 1, "false_positive": 0, "false_negative": 0,
        }

    def test_cluster_khong_khop_incident_nao_la_false_positive(self, tmp_path):
        path = _write_incidents(tmp_path, [_incident(signature="khac hoan toan")])
        result = evaluate([_cluster()], labeled_path=path)
        assert result["true_positive"] == 0
        assert result["false_positive"] == 1
        assert result["false_negative"] == 1

    def test_2_cluster_khop_cung_1_incident_khong_dem_trung_recall(self, tmp_path):
        """2 cluster cung khop 1 incident (vd 2 lan tinh lai cung signature)
        van chi tinh la 1 incident duoc phat hien (recall dung theo so incident,
        khong theo so cluster) nhung ca 2 cluster deu la true_positive."""
        path = _write_incidents(tmp_path, [_incident()])
        result = evaluate([_cluster(), _cluster(first_seen="2026-10-12T09:03:00Z")], labeled_path=path)
        assert result["true_positive"] == 2
        assert result["false_negative"] == 0
        assert result["recall"] == 1.0


class TestWithService:
    def test_cluster_da_co_service_tra_ve_nguyen(self):
        cluster = {"service": "demo-web", "log_ids": ["1"]}
        assert _with_service(cluster) == cluster

    def test_cluster_khong_co_log_ids_tra_ve_nguyen(self):
        cluster = {"log_ids": []}
        assert _with_service(cluster) == cluster

    def test_cluster_chua_co_service_tra_cuu_tu_log_store(self, monkeypatch):
        class _FakeStore:
            def get_by_ids(self, ids):
                assert ids == ["log-1"]
                return [{"log_id": "log-1", "service": "demo-mobile-api"}]

        import ingestion.src.storage as storage_module

        monkeypatch.setattr(storage_module, "get_store", lambda: _FakeStore())

        cluster = {"log_ids": ["log-1", "log-2"]}
        result = _with_service(cluster)
        assert result["service"] == "demo-mobile-api"

"""Test cho clustering/src/anomaly_score.py - cong thuc z-score va tinh
on dinh cua cluster_id, phan lo gic trung tam nhat cua ca he thong."""

from __future__ import annotations

from clustering.src.anomaly_score import _stable_cluster_id, compute_anomaly_score


def _log(log_id: str, ts: str, service: str = "demo-web", trace_id: str | None = None) -> dict:
    log = {"log_id": log_id, "timestamp": ts, "service": service, "message": "x"}
    if trace_id:
        log["trace_id"] = trace_id
    return log


class TestStableClusterId:
    def test_cung_service_signature_cung_id(self):
        assert _stable_cluster_id("demo-web", "sig-x") == _stable_cluster_id("demo-web", "sig-x")

    def test_khac_service_khac_id_du_cung_signature(self):
        assert _stable_cluster_id("demo-web", "sig-x") != _stable_cluster_id("demo-mobile-api", "sig-x")

    def test_khac_signature_khac_id_du_cung_service(self):
        assert _stable_cluster_id("demo-web", "sig-x") != _stable_cluster_id("demo-web", "sig-y")


class TestComputeAnomalyScore:
    def test_khong_co_baseline_score_bang_count(self):
        logs = [_log("1", "2026-10-12T09:00:00Z"), _log("2", "2026-10-12T09:01:00Z")]
        result = compute_anomaly_score("sig-x", logs, baseline_mean=0.0, baseline_stdev=0.0)
        assert result["score"] == 2.0
        assert result["status"] == "normal"

    def test_stdev_0_mean_0_dung_ty_le_lech(self):
        logs = [_log(str(i), "2026-10-12T09:00:00Z") for i in range(6)]
        result = compute_anomaly_score("sig-x", logs, baseline_mean=3.0, baseline_stdev=0.0)
        assert result["score"] == 1.0  # (6-3)/3

    def test_co_stdev_dung_z_score(self):
        logs = [_log(str(i), "2026-10-12T09:00:00Z") for i in range(10)]
        result = compute_anomaly_score("sig-x", logs, baseline_mean=4.0, baseline_stdev=2.0)
        assert result["score"] == 3.0  # (10-4)/2

    def test_score_khong_am_khi_count_duoi_baseline(self):
        logs = [_log("1", "2026-10-12T09:00:00Z")]
        result = compute_anomaly_score("sig-x", logs, baseline_mean=10.0, baseline_stdev=2.0)
        assert result["score"] == 0.0

    def test_cluster_id_on_dinh_theo_service_dau_tien(self):
        logs = [_log("1", "2026-10-12T09:00:00Z", service="demo-mobile-api")]
        result = compute_anomaly_score("sig-x", logs)
        assert result["cluster_id"] == _stable_cluster_id("demo-mobile-api", "sig-x")
        assert result["service"] == "demo-mobile-api"

    def test_first_seen_last_seen_log_ids_trace_ids_sap_xep(self):
        logs = [
            _log("b", "2026-10-12T09:05:00Z", trace_id="tb"),
            _log("a", "2026-10-12T09:00:00Z", trace_id="ta"),
        ]
        result = compute_anomaly_score("sig-x", logs)
        assert result["first_seen"] == "2026-10-12T09:00:00Z"
        assert result["last_seen"] == "2026-10-12T09:05:00Z"
        assert result["log_ids"] == ["a", "b"]
        assert result["trace_ids"] == ["ta", "tb"]

    def test_danh_sach_log_rong(self):
        result = compute_anomaly_score("sig-x", [])
        assert result["score"] == 0.0
        assert result["log_ids"] == []
        assert result["service"] == ""

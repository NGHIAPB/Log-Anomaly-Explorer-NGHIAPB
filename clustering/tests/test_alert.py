"""Test cho clustering/src/alert.py - nguong alert va gui webhook.

ANOMALY_THRESHOLD/ALERT_WEBHOOK_URL duoc doc tu os.environ LUC MODULE duoc
import, nen de doi hanh vi trong test phai monkeypatch truc tiep bien cua
module (clustering.src.alert.X), khong phai monkeypatch.setenv."""

from __future__ import annotations

import clustering.src.alert as alert_module
from clustering.src.alert import check_and_alert


def _cluster(score: float) -> dict:
    return {"cluster_id": "c1", "score": score, "service": "demo-web", "first_seen": "2026-10-12T09:00:00Z", "status": "normal"}


class TestCheckAndAlert:
    def test_score_0_status_normal_khong_alert(self, monkeypatch):
        monkeypatch.setattr(alert_module, "ANOMALY_THRESHOLD", 2.0)
        cluster = _cluster(0.0)
        assert check_and_alert(cluster) is False
        assert cluster["status"] == "normal"

    def test_score_duoi_nguong_status_anomalous_khong_alert(self, monkeypatch):
        monkeypatch.setattr(alert_module, "ANOMALY_THRESHOLD", 2.0)
        cluster = _cluster(1.5)
        assert check_and_alert(cluster) is False
        assert cluster["status"] == "anomalous"

    def test_score_vuot_nguong_khong_co_webhook_status_alerted_nhung_khong_gui(self, monkeypatch):
        monkeypatch.setattr(alert_module, "ANOMALY_THRESHOLD", 2.0)
        monkeypatch.setattr(alert_module, "ALERT_WEBHOOK_URL", "")
        cluster = _cluster(5.0)
        assert check_and_alert(cluster) is False
        assert cluster["status"] == "alerted"

    def test_score_vuot_nguong_co_webhook_goi_httpx_post(self, monkeypatch):
        monkeypatch.setattr(alert_module, "ANOMALY_THRESHOLD", 2.0)
        monkeypatch.setattr(alert_module, "ALERT_WEBHOOK_URL", "https://example.test/webhook")

        calls = []

        def fake_post(url, json=None, timeout=None):
            calls.append((url, json))

        monkeypatch.setattr(alert_module.httpx, "post", fake_post)

        cluster = _cluster(5.0)
        assert check_and_alert(cluster) is True
        assert cluster["status"] == "alerted"
        assert len(calls) == 1
        assert calls[0][0] == "https://example.test/webhook"
        assert calls[0][1]["cluster_id"] == "c1"

    def test_webhook_loi_tra_ve_false_khong_crash(self, monkeypatch):
        import httpx

        monkeypatch.setattr(alert_module, "ANOMALY_THRESHOLD", 2.0)
        monkeypatch.setattr(alert_module, "ALERT_WEBHOOK_URL", "https://example.test/webhook")

        def fake_post_loi(url, json=None, timeout=None):
            raise httpx.ConnectError("khong ket noi duoc")

        monkeypatch.setattr(alert_module.httpx, "post", fake_post_loi)

        cluster = _cluster(5.0)
        assert check_and_alert(cluster) is False
        assert cluster["status"] == "alerted"

    def test_nguong_bang_score_khong_alert(self, monkeypatch):
        """score <= threshold moi khong alert (bien, dung '<=' trong code)."""
        monkeypatch.setattr(alert_module, "ANOMALY_THRESHOLD", 2.0)
        cluster = _cluster(2.0)
        assert check_and_alert(cluster) is False
        assert cluster["status"] == "anomalous"

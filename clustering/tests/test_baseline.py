"""Test cho clustering/src/baseline.py - tinh baseline tan suat lich su
(mean/stdev theo bucket thoi gian) lam dau vao cho anomaly_score."""

from __future__ import annotations

from clustering.src.baseline import bucket_key, compute_baseline, historical_bucket_counts


class TestBucketKey:
    def test_cung_1_bucket_10_phut(self):
        b1 = bucket_key("2026-10-12T09:00:00Z", bucket_minutes=10)
        b2 = bucket_key("2026-10-12T09:05:00Z", bucket_minutes=10)
        assert b1 == b2

    def test_khac_bucket_khi_qua_mep(self):
        b1 = bucket_key("2026-10-12T09:09:59Z", bucket_minutes=10)
        b2 = bucket_key("2026-10-12T09:10:01Z", bucket_minutes=10)
        assert b1 != b2


class TestHistoricalBucketCounts:
    def _log(self, ts: str, service: str, message: str) -> dict:
        return {"timestamp": ts, "service": service, "message": message}

    def test_dem_dung_theo_service_va_signature_khong_tinh_bucket_hien_tai(self):
        current_bucket = bucket_key("2026-10-12T10:00:00Z", bucket_minutes=10)
        history = [
            self._log("2026-10-12T09:50:00Z", "demo-web", "Simulated downstream failure"),  # bucket -1
            self._log("2026-10-12T09:40:00Z", "demo-web", "Simulated downstream failure"),  # bucket -2
            self._log("2026-10-12T10:00:00Z", "demo-web", "Simulated downstream failure"),  # bucket hien tai, bo qua
            self._log("2026-10-12T09:50:00Z", "demo-mobile-api", "Simulated downstream failure"),  # service khac
        ]
        counts = historical_bucket_counts(
            history, service="demo-web", signature="simulated downstream failure",
            bucket_minutes=10, num_buckets=3, current_bucket=current_bucket,
        )
        assert counts == [1, 1, 0]

    def test_bucket_rong_tra_ve_0_khong_bi_bo_qua(self):
        current_bucket = bucket_key("2026-10-12T10:00:00Z", bucket_minutes=10)
        counts = historical_bucket_counts(
            [], service="demo-web", signature="x", bucket_minutes=10, num_buckets=5,
            current_bucket=current_bucket,
        )
        assert counts == [0, 0, 0, 0, 0]

    def test_loc_theo_service_2_service_cung_signature_khong_gop(self):
        """Khop voi fix group_similar_errors (service, signature): baseline
        cua 1 service khong bi 'nhiem' log cua service khac cung signature."""
        current_bucket = bucket_key("2026-10-12T10:00:00Z", bucket_minutes=10)
        history = [self._log("2026-10-12T09:50:00Z", "demo-mobile-api", "Simulated downstream failure")]
        counts = historical_bucket_counts(
            history, service="demo-web", signature="simulated downstream failure",
            bucket_minutes=10, num_buckets=1, current_bucket=current_bucket,
        )
        assert counts == [0]


class TestComputeBaseline:
    def test_khong_co_lich_su_tra_ve_0_0(self):
        assert compute_baseline([]) == {"mean": 0.0, "stdev": 0.0}

    def test_1_phan_tu_stdev_0(self):
        result = compute_baseline([5])
        assert result == {"mean": 5.0, "stdev": 0.0}

    def test_nhieu_phan_tu_tinh_dung_mean_stdev(self):
        result = compute_baseline([2, 4, 4, 4, 5, 5, 7, 9])
        assert result["mean"] == 5.0
        assert round(result["stdev"], 4) == 2.0

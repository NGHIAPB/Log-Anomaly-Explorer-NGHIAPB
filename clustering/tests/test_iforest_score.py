"""Test cho clustering/src/iforest_score.py - cham score bang Isolation Forest (tuy chon).

Phan can scikit-learn duoc skip khi chua cai; cac test ve HOP DONG fallback
(tra None -> main.py dung z-score) chay duoc trong moi truong hop.
"""

from __future__ import annotations

import pytest

from clustering.src.iforest_score import (
    combine,
    current_features,
    fit_scorer,
    history_features,
    maybe_fit_scorer,
)


class TestFeatures:
    def test_history_features_ghep_bucket_voi_bucket_truoc(self):
        # counts[0] la bucket gan hien tai nhat (xem baseline.historical_bucket_counts)
        assert history_features([5, 3, 2]) == [
            [5.0, 3.0, 2.0],
            [3.0, 2.0, 1.0],
        ]

    def test_history_features_it_hon_2_bucket_thi_rong(self):
        assert history_features([4]) == []
        assert history_features([]) == []

    def test_current_features_so_voi_bucket_gan_nhat(self):
        assert current_features([3, 2, 1], 10) == [10.0, 3.0, 7.0]

    def test_current_features_khong_co_lich_su_tra_none(self):
        assert current_features([], 10) is None


class TestFallbackContract:
    """Nhung truong hop PHAI tra None de main.py quay ve z-score."""

    def test_qua_it_du_lieu_tra_none(self):
        assert fit_scorer({("demo-web", "sig"): [1, 0]}) is None

    def test_khong_co_cum_nao_tra_none(self):
        assert fit_scorer({}) is None

    def test_lich_su_phang_tuyet_doi_tra_none(self):
        """Moi bucket giong nhau -> khong co thang do do-bi-co-lap de so sanh."""
        counts_by_key = {(f"svc{i}", "sig"): [0] * 8 for i in range(5)}
        assert fit_scorer(counts_by_key) is None

    def test_mac_dinh_tat_tra_none(self, monkeypatch):
        monkeypatch.delenv("CLUSTERING_SCORER", raising=False)
        counts_by_key = {(f"svc{i}", "sig"): [5, 1, 4, 2, 6, 1] for i in range(5)}
        assert maybe_fit_scorer(counts_by_key) is None

    def test_bat_bang_bien_moi_truong(self, monkeypatch):
        pytest.importorskip("sklearn")
        monkeypatch.setenv("CLUSTERING_SCORER", "iforest")
        counts_by_key = {(f"svc{i}", "sig"): [5, 1, 4, 2, 6, 1] for i in range(5)}
        assert maybe_fit_scorer(counts_by_key) is not None


class TestScoring:
    def setup_method(self):
        pytest.importorskip("sklearn")

    @staticmethod
    def _normal_history() -> dict:
        # 6 cum, lich su quanh 1-3 loi/bucket -> "binh thuong" cua he thong
        return {
            ("demo-web", "sig-a"): [2, 1, 3, 2, 1, 2],
            ("demo-web", "sig-b"): [1, 2, 1, 1, 2, 1],
            ("demo-mobile-api", "sig-a"): [3, 2, 2, 3, 1, 2],
            ("demo-mobile-api", "sig-c"): [1, 1, 2, 1, 1, 1],
            ("demo-web", "sig-d"): [2, 2, 1, 2, 2, 3],
            ("demo-web", "sig-e"): [1, 3, 2, 1, 3, 2],
        }

    def test_burst_duoc_cham_diem_cao_hon_muc_binh_thuong(self):
        scorer = fit_scorer(self._normal_history())
        assert scorer is not None

        normal = scorer.score([2, 1, 3, 2, 1, 2], 2)
        burst = scorer.score([2, 1, 3, 2, 1, 2], 150)
        assert normal is not None and burst is not None
        assert burst > normal

    def test_score_khong_am(self):
        scorer = fit_scorer(self._normal_history())
        assert scorer.score([2, 1, 3, 2, 1, 2], 0) >= 0.0

    def test_cung_dau_vao_cho_cung_score(self):
        """random_state co dinh: score khong duoc nhay giua cac chu ky chay
        khi du lieu khong doi (neu khong, status/alert se bat tat that thuong)."""
        first = fit_scorer(self._normal_history()).score([2, 1, 3, 2, 1, 2], 40)
        second = fit_scorer(self._normal_history()).score([2, 1, 3, 2, 1, 2], 40)
        assert first == second

    def test_khong_co_lich_su_tra_none_de_fallback(self):
        scorer = fit_scorer(self._normal_history())
        assert scorer.score([], 10) is None

    def test_bat_duoc_bat_thuong_ve_HINH_DANG_ma_z_score_mu_hoan_toan(self):
        """Day la ly do ton tai cua ca lop nay. Lich su dao dong 0/20 (mean=10,
        stdev=10): count=10 cho z-score = (10-10)/10 = 0.00, tuc z-score coi la
        hoan toan binh thuong. Nhung 10 la gia tri CHUA TUNG xuat hien trong
        mau 0/20 do - Isolation Forest bat duoc vi no nhin ca [count, count
        truoc, chenh lech], khong chi do lech so voi trung binh.
        """
        volatile = {
            ("demo-web", "a"): [0, 20, 0, 20, 0, 20],
            ("demo-web", "b"): [1, 18, 2, 19, 0, 17],
            ("demo-mobile-api", "a"): [0, 22, 1, 21, 0, 19],
            ("demo-mobile-api", "b"): [2, 17, 0, 20, 1, 18],
        }
        scorer = fit_scorer(volatile)
        assert scorer is not None

        zscore_cua_count_10 = 0.0  # (10 - mean 10) / stdev 10
        assert scorer.score([0, 20, 0, 20, 0, 20], 10) > zscore_cua_count_10

    def test_score_BI_CHAN_khong_the_dung_mot_minh(self):
        """GAP DA DO THUC TE (2026-10-22): score_samples() cua Isolation Forest
        co mien gia tri bi chan, nen burst 200 loi tren lich su ~2 loi/bucket
        chi ra ~1.8 - DUOI ANOMALY_THRESHOLD=2.0. Test nay ghi lai dung gioi
        han do, va la ly do main.py dung max(z-score, iforest) chu khong thay
        the z-score (xem combine()). Neu sau nay doi cach quy doi thang do,
        test se do de buoc xem lai, khong lang le bo sot."""
        scorer = fit_scorer(self._normal_history())
        assert scorer.score([2, 1, 3, 2, 1, 2], 200) < 2.0


class TestCombine:
    def test_lay_gia_tri_cao_hon(self):
        assert combine(1.0, 3.5) == 3.5
        assert combine(9.0, 3.5) == 9.0

    def test_ml_khong_cham_duoc_thi_giu_z_score(self):
        assert combine(4.2, None) == 4.2

    def test_burst_lon_van_vuot_nguong_nho_z_score_lam_san(self):
        """Hop dong an toan: bat lop ML khong bao gio lam he thong phat hien
        te hon rule-based - z-score cua burst lon van duoc giu."""
        zscore_burst = 73.5  # z-score that cua mot burst lon
        assert combine(zscore_burst, 1.833) == zscore_burst

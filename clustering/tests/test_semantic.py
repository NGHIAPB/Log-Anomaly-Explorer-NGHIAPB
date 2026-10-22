"""Test cho clustering/src/semantic.py - lop gop cum theo ngu nghia (tuy chon).

Dung embedder GIA (vector dat tay) thay vi tai model that: test phai chay duoc
khi chua cai sentence-transformers/torch, va phai xac dinh (khong phu thuoc
model tai ve). Phan phan cum that (scikit-learn) van duoc chay.
"""

from __future__ import annotations

import pytest

from clustering.src import semantic
from clustering.src.semantic import identity_members, maybe_merge_semantic, merge_similar_groups

pytest.importorskip("sklearn", reason="lop semantic can scikit-learn de phan cum")

# Cosine similarity giua cac vector nay (da do): A-B=0.90, A-C=0.80,
# B-C=0.98, A-D=0.00 - phan tan du de test nguong co y nghia.
_A = "connection refused by downstream"
_B = "downstream dependency unreachable"
_C = "cannot reach downstream service"
_D = "user <num> not found"

_VECTORS = {
    _A: [1.0, 0.0, 0.0],
    _B: [0.9, 0.436, 0.0],
    _C: [0.8, 0.6, 0.0],
    _D: [0.0, 0.0, 1.0],
}


def _fake_embed(texts):
    return [_VECTORS[text] for text in texts]


def _log(log_id: str, service: str = "demo-web") -> dict:
    return {
        "log_id": log_id,
        "timestamp": "2026-10-22T09:00:00Z",
        "level": "ERROR",
        "service": service,
        "message": "x",
    }


def _groups(*signatures: str, service: str = "demo-web") -> dict:
    return {(service, sig): [_log(str(i))] for i, sig in enumerate(signatures)}


class TestMergeSimilarGroups:
    def test_gop_signature_gan_nghia_giu_rieng_signature_khac_biet(self):
        merged, members = merge_similar_groups(_groups(_A, _B, _C, _D), embed=_fake_embed)

        # 3 signature ve downstream (sim >= 0.8) gop lai; "user not found" (sim 0) giu rieng.
        assert len(merged) == 2
        assert ("demo-web", _D) in merged
        # Dai dien la signature nho nhat theo thu tu chu trong nhom da gop.
        assert ("demo-web", _C) in merged
        assert len(merged[("demo-web", _C)]) == 3
        assert members[("demo-web", _C)] == sorted([_A, _B, _C])
        assert members[("demo-web", _D)] == [_D]

    def test_nguong_cao_hon_thi_gop_it_hon(self, monkeypatch):
        """MIN_SIMILARITY la nut dieu khien duy nhat: nang len thi cac signature
        chi hoi giong nhau phai duoc tach ra."""
        monkeypatch.setattr(semantic, "MIN_SIMILARITY", 0.88)
        merged, members = merge_similar_groups(_groups(_A, _B, _C, _D), embed=_fake_embed)

        # A-{B,C} co khoang cach trung binh 0.15 > 1-0.88 -> A tach rieng.
        assert len(merged) == 3
        assert members[("demo-web", _C)] == sorted([_B, _C])
        assert members[("demo-web", _A)] == [_A]
        assert members[("demo-web", _D)] == [_D]

    def test_chan_gop_sai_khi_signature_khong_du_giong_dai_dien(self, monkeypatch):
        """Lop chan cuoi: neu buoc phan cum de xuat gop 2 signature khong lien
        quan (khong gian embedding thua), similarity guard phai tach chung ra."""
        monkeypatch.setattr(semantic, "_cluster_labels", lambda vectors: [0] * len(vectors))
        merged, members = merge_similar_groups(_groups(_A, _D), embed=_fake_embed)

        assert len(merged) == 2
        assert members[("demo-web", _A)] == [_A]
        assert members[("demo-web", _D)] == [_D]

    def test_dai_dien_khong_phu_thuoc_thu_tu_duyet_dict(self):
        """cluster_id sinh tu signature dai dien, nen chon dai dien phai xac
        dinh - neu khong cluster_id se nhay giua cac lan chay (xem
        anomaly_score._stable_cluster_id)."""
        forward, _ = merge_similar_groups(_groups(_A, _B, _C), embed=_fake_embed)
        backward, _ = merge_similar_groups(_groups(_C, _B, _A), embed=_fake_embed)
        assert set(forward) == set(backward)

    def test_khong_gop_cheo_service(self):
        groups = {
            ("demo-web", _A): [_log("1")],
            ("demo-mobile-api", _B): [_log("2", service="demo-mobile-api")],
        }
        merged, members = merge_similar_groups(groups, embed=_fake_embed)
        assert set(merged) == set(groups)
        assert members == identity_members(groups)

    def test_mot_signature_duy_nhat_khong_doi(self):
        groups = _groups(_D)
        merged, members = merge_similar_groups(groups, embed=_fake_embed)
        assert merged == groups
        assert members == {("demo-web", _D): [_D]}


class TestMaybeMergeSemantic:
    def test_mac_dinh_tat_tra_nguyen_groups(self, monkeypatch):
        monkeypatch.delenv("CLUSTERING_SEMANTIC_MERGE", raising=False)
        groups = _groups(_A, _B)
        merged, members = maybe_merge_semantic(groups)
        assert merged == groups
        assert members == identity_members(groups)

    def test_bat_nhung_thieu_thu_vien_thi_fallback_rule_based(self, monkeypatch):
        """Duong fallback quan trong nhat: bat len tren may chua cai
        sentence-transformers thi job phai chay tiep bang rule-based, khong sap."""
        monkeypatch.setenv("CLUSTERING_SEMANTIC_MERGE", "true")

        def _boom(_texts):
            raise ImportError("sentence_transformers chua duoc cai")

        monkeypatch.setattr(semantic, "default_embedder", _boom)

        groups = _groups(_A, _B)
        merged, members = maybe_merge_semantic(groups)
        assert merged == groups
        assert members == identity_members(groups)

    def test_bat_va_chay_duoc_thi_co_gop(self, monkeypatch):
        monkeypatch.setenv("CLUSTERING_SEMANTIC_MERGE", "true")
        monkeypatch.setattr(semantic, "default_embedder", _fake_embed)
        merged, _ = maybe_merge_semantic(_groups(_A, _B, _C, _D))
        assert len(merged) == 2

    def test_groups_rong(self, monkeypatch):
        monkeypatch.setenv("CLUSTERING_SEMANTIC_MERGE", "true")
        assert maybe_merge_semantic({}) == ({}, {})

"""
Gop cum theo NGU NGHIA - lop TUY CHON dat TREN thuat toan rule-based trong
clustering.py, khong thay the no.

Vi sao can: normalize_message() chi gop duoc cac loi co cung "hinh dang" sau
khi thay the gia tri dong (so, uuid, chuoi trong quote). Hai message dien dat
KHAC NHAU nhung cung mot van de - vi du "Connection refused by downstream"
va "Downstream dependency unreachable" - van ra 2 signature khac nhau, tuc 2
cum rieng. Lop nay dung sentence embedding (all-MiniLM-L6-v2) de phat hien
cac signature gan nhau ve nghia va gop chung lai.

Vi sao dung agglomerative clustering (khong dung HDBSCAN): moi service trong
mot khung thoi gian thuong chi co vai signature khac nhau. Da do thuc te o
quy mo nay (4 signature): HDBSCAN gan TAT CA la nhieu (-1) nen khong gop
duoc gi - no can mat do du lieu du day, khong phu hop voi N nho. Agglomerative
voi nguong khoang cach cosine lai dien dat dung y muon can: "gop cac signature
co cosine similarity >= CLUSTERING_SEMANTIC_MIN_SIMILARITY", chi mot tham so
duy nhat de giai thich va dieu chinh.

MAC DINH TAT. Bat bang CLUSTERING_SEMANTIC_MERGE=true.
Ly do mac dinh tat: gop lam DOI signature cua cum -> doi cluster_id (xem
anomaly_score._stable_cluster_id) -> cac ClusterRecord dang co tren ban deploy
that va `expected_cluster_signature` trong evaluation/labeled_incidents.json
se khong con khop. Chi bat khi da chu dong chap nhan dieu do.

Moi tinh huong bat trac (thieu thu vien, model tai that bai, embedding loi)
deu KHONG lam sap job: ham tra ve dung groups rule-based ban dau.

Cai dat phu thuoc (keo theo torch, ~1GB):
    pip install -r clustering/requirements-ml.txt
"""

from __future__ import annotations

import math
import os
from collections import defaultdict
from typing import Callable, Iterable, Sequence

GroupKey = tuple[str, str]
Embedder = Callable[[Sequence[str]], list[Sequence[float]]]

MODEL_NAME = os.environ.get("CLUSTERING_SEMANTIC_MODEL", "all-MiniLM-L6-v2")
# Nguong duy nhat dieu khien viec gop: 2 signature chi ve cung mot cum khi
# cosine similarity >= nguong nay. 0.75 = kha giong nhau ve nghia.
MIN_SIMILARITY = float(os.environ.get("CLUSTERING_SEMANTIC_MIN_SIMILARITY", "0.75"))

_model = None


def _enabled() -> bool:
    return os.environ.get("CLUSTERING_SEMANTIC_MERGE", "false").strip().lower() == "true"


def _get_model():
    """Tai model mot lan cho ca process (tai model ton ~1-2s va vai tram MB RAM)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def default_embedder(texts: Sequence[str]) -> list[Sequence[float]]:
    return [list(vector) for vector in _get_model().encode(list(texts))]


def _unit(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else [0.0 for _ in vector]


def _cluster_labels(vectors: Sequence[Sequence[float]]) -> list[int]:
    """Nhan cum cho tung vector (signature nao ve cung mot cum).

    distance_threshold = 1 - MIN_SIMILARITY: tren vector don vi, cosine
    distance = 1 - cosine similarity, nen nguong nay dung bang nguong
    similarity da khai bao o tren. linkage="average" de mot signature lech
    khong keo ca cum di theo.
    """
    from sklearn.cluster import AgglomerativeClustering

    model = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=1.0 - MIN_SIMILARITY,
        metric="cosine",
        linkage="average",
    )
    return [int(label) for label in model.fit_predict([list(v) for v in vectors])]


def merge_similar_groups(
    groups: dict[GroupKey, list[dict]], *, embed: Embedder
) -> tuple[dict[GroupKey, list[dict]], dict[GroupKey, list[str]]]:
    """Gop cac nhom cung service co signature tuong dong ve nghia.

    `embed` nhan danh sach signature, tra ve vector cho tung signature.

    Tra ve (groups_sau_gop, members) voi members = {key: [signature goc da
    gop vao key]}. members can cho main.py cong don baseline lich su cua tung
    signature goc - neu chi dung signature dai dien thi lich su cua cac
    signature con lai bi bo qua, lam baseline thap gia tao.

    Chi gop trong cung mot service (khong gop cheo service) - giu dung ly do
    da neu trong clustering.group_similar_errors().
    """
    merged: dict[GroupKey, list[dict]] = {}
    members: dict[GroupKey, list[str]] = {}

    by_service: dict[str, list[str]] = defaultdict(list)
    for service, signature in groups:
        by_service[service].append(signature)

    for service, raw_signatures in sorted(by_service.items()):
        # sorted(set(...)): ket qua gop phai khong phu thuoc thu tu duyet dict,
        # de cung du lieu vao thi cung cluster_id ra o moi lan chay.
        signatures = sorted(set(raw_signatures))
        if len(signatures) < 2:
            for signature in signatures:
                merged[(service, signature)] = list(groups[(service, signature)])
                members[(service, signature)] = [signature]
            continue

        vectors = [_unit(vector) for vector in embed(signatures)]
        labels = _cluster_labels(vectors)

        buckets: dict[int, list[int]] = defaultdict(list)
        for index, label in enumerate(labels):
            buckets[label].append(index)

        # Cum chi co 1 signature -> kept = chinh no, ket qua y nguyen nhu
        # rule-based (khong co nhanh rieng cho truong hop nay).
        for indexes in buckets.values():
            canonical_index = min(indexes, key=lambda i: signatures[i])
            canonical = signatures[canonical_index]
            kept = [
                i
                for i in indexes
                if i == canonical_index
                or _cosine(vectors[i], vectors[canonical_index]) >= MIN_SIMILARITY
            ]
            for index in indexes:
                if index not in kept:
                    signature = signatures[index]
                    merged[(service, signature)] = list(groups[(service, signature)])
                    members[(service, signature)] = [signature]

            logs: list[dict] = []
            for index in sorted(kept, key=lambda i: signatures[i]):
                logs.extend(groups[(service, signatures[index])])
            merged[(service, canonical)] = logs
            members[(service, canonical)] = sorted(signatures[i] for i in kept)

    return merged, members


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def identity_members(groups: Iterable[GroupKey]) -> dict[GroupKey, list[str]]:
    return {key: [key[1]] for key in groups}


def maybe_merge_semantic(
    groups: dict[GroupKey, list[dict]],
) -> tuple[dict[GroupKey, list[dict]], dict[GroupKey, list[str]]]:
    """Gop theo nghia neu da bat va chay duoc; nguoc lai tra nguyen groups.

    Day la diem duy nhat main.py goi - moi quyet dinh bat/tat va moi fallback
    nam o day, de luong rule-based trong main.py khong doi.
    """
    if not _enabled() or not groups:
        return groups, identity_members(groups)
    try:
        return merge_similar_groups(groups, embed=default_embedder)
    except Exception as exc:  # job nen: khong duoc sap vi lop tuy chon nay
        print(f"[clustering] semantic merge bi bo qua, dung rule-based: {type(exc).__name__}: {exc}")
        return groups, identity_members(groups)

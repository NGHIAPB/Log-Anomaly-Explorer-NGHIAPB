"""
Clustering / Anomaly Score / Alert - job nen (khong phai HTTP service), Nam.

Doc log ERROR/FATAL moi tu LogStore cua Ingestion (Minh), nhom theo loi
tuong tu (clustering.py), tinh baseline tan suat lich su that (baseline.py),
cham anomaly score (anomaly_score.py), phat alert khi vuot nguong (alert.py),
roi ghi ClusterRecord vao ClusterStore (storage.py) de Nghia doc phuc vu
Incident View (xem docs/architect/contracts/api-contract.md).

Chay thu (tu thu muc goc repo, de import package hoat dong):
    python -m clustering.src.main                 # loop vo han, moi CLUSTERING_INTERVAL_SECONDS
    CLUSTERING_INTERVAL_SECONDS=0 python -m clustering.src.main   # chay 1 lan roi thoat

Bien moi truong (xem clustering/README.md):
    CLUSTERING_WINDOW_MINUTES (mac dinh 10) - do dai khung thoi gian dang xet.
    CLUSTERING_BASELINE_WINDOWS (mac dinh 6) - so khung lich su dung tinh baseline.
    CLUSTERING_INTERVAL_SECONDS (mac dinh 60) - khoang nghi giua 2 lan chay; 0 = chay 1 lan.
    CLUSTERING_FETCH_SIZE (mac dinh 5000) - so log toi da doc mot lan tu LogStore.

Hai lop ML TUY CHON, mac dinh TAT (xem clustering/README.md muc "Lop ML tuy chon"):
    CLUSTERING_SEMANTIC_MERGE=true  - gop cum theo ngu nghia (semantic.py).
    CLUSTERING_SCORER=iforest       - cham score bang Isolation Forest (iforest_score.py).
Ca hai deu tu quay ve luong rule-based khi thieu thu vien hoac gap loi.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

from ingestion.src.storage import get_store

from .alert import check_and_alert
from .anomaly_score import compute_anomaly_score
from .baseline import bucket_key, compute_baseline, historical_bucket_counts
from .clustering import group_similar_errors
from .iforest_score import combine, maybe_fit_scorer
from .semantic import maybe_merge_semantic
from .storage import get_cluster_store

WINDOW_MINUTES = float(os.environ.get("CLUSTERING_WINDOW_MINUTES", "10"))
BASELINE_WINDOWS = int(os.environ.get("CLUSTERING_BASELINE_WINDOWS", "6"))
INTERVAL_SECONDS = float(os.environ.get("CLUSTERING_INTERVAL_SECONDS", "60"))
FETCH_SIZE = int(os.environ.get("CLUSTERING_FETCH_SIZE", "5000"))

_ERROR_LEVELS = ("ERROR", "FATAL")


def run_once(now: datetime | None = None) -> list[dict]:
    """Chay mot lan: doc logs, nhom, cham score, alert, ghi ClusterRecord.

    Tra ve danh sach cluster da tinh trong lan nay (BAO GOM truong noi bo
    "service", dung cho alert/eval - khac voi ban ghi da "lam sach" theo
    schema duoc ghi vao ClusterStore, xem storage.to_cluster_record()).
    """
    now = now or datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=WINDOW_MINUTES)
    history_start = window_start - timedelta(minutes=WINDOW_MINUTES * BASELINE_WINDOWS)

    log_store = get_store()
    cluster_store = get_cluster_store()

    all_logs = log_store.search(
        time_from=history_start.isoformat(),
        time_to=now.isoformat(),
        size=FETCH_SIZE,
    )
    error_logs = [l for l in all_logs if l.get("level") in _ERROR_LEVELS]
    window_start_iso = window_start.isoformat()
    current_logs = [l for l in error_logs if l.get("timestamp", "") >= window_start_iso]
    history_logs = [l for l in error_logs if l.get("timestamp", "") < window_start_iso]

    groups = group_similar_errors(current_logs)
    # Lop ML tuy chon, mac dinh TAT -> tra lai dung groups rule-based
    # (xem semantic.py, iforest_score.py).
    groups, members = maybe_merge_semantic(groups)
    current_bucket = bucket_key(now.isoformat(), WINDOW_MINUTES)

    # Cong don lich su theo TUNG signature goc da gop vao cum: neu chi dem
    # theo signature dai dien thi lich su cua cac signature con lai bi bo
    # qua, baseline thap gia tao -> score cao gia tao. Khi khong gop (mac
    # dinh), members[key] chi co dung 1 signature nen ket qua khong doi.
    counts_by_key: dict[tuple[str, str], list[int]] = {}
    for key, signatures in members.items():
        per_signature = [
            historical_bucket_counts(
                history_logs, key[0], signature, WINDOW_MINUTES, BASELINE_WINDOWS, current_bucket
            )
            for signature in signatures
        ]
        counts_by_key[key] = [sum(values) for values in zip(*per_signature)]

    scorer = maybe_fit_scorer(counts_by_key)

    results: list[dict] = []
    for (service, signature), logs in groups.items():
        counts = counts_by_key[(service, signature)]
        baseline = compute_baseline(counts)
        record = compute_anomaly_score(signature, logs, baseline["mean"], baseline["stdev"])
        if scorer is not None:
            # max(z-score, iforest): lop ML chi lam TANG do nhay, khong bao
            # gio lam giam (xem docstring iforest_score.py).
            record["score"] = round(combine(record["score"], scorer.score(counts, len(logs))), 3)
        check_and_alert(record)
        cluster_store.write_cluster(record)
        results.append(record)
    return results


def run_forever() -> None:
    if INTERVAL_SECONDS <= 0:
        run_once()
        return
    while True:
        try:
            run_once()
        except Exception as exc:  # job nen: 1 lan chay loi khong duoc lam chet job
            print(f"[clustering] run_once failed: {exc}")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    run_forever()

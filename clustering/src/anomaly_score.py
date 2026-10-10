"""
Tinh Anomaly Score cho tung cum loi, dua tren baseline tan suat lich su that
(xem baseline.py) thay vi mot ty le dem don gian.

Cong thuc: z-score cua so luong log trong khung hien tai so voi
(mean, stdev) cua lich su cung signature:

    score = max(0, (count - mean) / stdev)          neu stdev > 0
    score = max(0, (count - mean) / mean)            neu stdev == 0 va mean > 0
                                                       (lich su on dinh tuyet doi,
                                                       dung ty le lech thay z-score)
    score = count                                     neu mean == 0 (signature
                                                       moi, chua co lich su - ban
                                                       than viec no xuat hien da
                                                       la bat thuong, muc do theo so luong)
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def _stable_cluster_id(service: str, signature: str) -> str:
    """Id on dinh theo (service, signature) de cung mot loai loi xay ra
    nhieu lan o nhieu khung thoi gian khac nhau duoc cap nhat vao MOT
    ClusterRecord (incident dang tiep dien) thay vi tao cum moi moi lan.
    """
    digest = hashlib.sha1(f"{service}:{signature}".encode("utf-8")).hexdigest()
    return digest[:32]


def compute_anomaly_score(
    signature: str,
    logs: list[dict],
    baseline_mean: float = 0.0,
    baseline_stdev: float = 0.0,
) -> dict:
    """Tra ve mot ClusterRecord (dung theo docs/architect/contracts/cluster-record.schema.json).

    `logs`: cac log ERROR/FATAL cung signature trong khung thoi gian hien tai.
    `baseline_mean`/`baseline_stdev`: lay tu baseline.compute_baseline() tren
    lich su cung signature (xem src/main.py cho cach tinh tu du lieu that).

    Luu y: ket qua co them key "service" (lay tu log dau tien) de alert.py
    va evaluation/precision_recall.py dung - KHONG nam trong
    cluster-record.schema.json (additionalProperties: false) nen storage.py
    se loai bo truong nay truoc khi ghi vao ClusterStore.
    """
    count = len(logs)
    service = logs[0].get("service", "") if logs else ""

    if baseline_stdev > 0:
        score = max(0.0, (count - baseline_mean) / baseline_stdev)
    elif baseline_mean > 0:
        score = max(0.0, (count - baseline_mean) / baseline_mean)
    else:
        score = float(count)

    timestamps = sorted(log["timestamp"] for log in logs)
    log_ids = sorted({log["log_id"] for log in logs if log.get("log_id")})
    trace_ids = sorted({log["trace_id"] for log in logs if log.get("trace_id")})

    return {
        "cluster_id": _stable_cluster_id(service, signature),
        "signature": signature,
        "score": round(score, 3),
        "log_ids": log_ids,
        "trace_ids": trace_ids,
        "first_seen": timestamps[0] if timestamps else datetime.now(timezone.utc).isoformat(),
        "last_seen": timestamps[-1] if timestamps else datetime.now(timezone.utc).isoformat(),
        "status": "normal",
        "service": service,
    }

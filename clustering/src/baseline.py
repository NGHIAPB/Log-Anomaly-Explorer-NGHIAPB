"""
Baseline tan suat lich su cho tung signature loi.

Thay cho placeholder (mot so baseline_rate co dinh truyen tay), module nay
tinh baseline THAT bang cach chia lich su log loi (ERROR/FATAL) truoc khung
hien tai thanh cac "bucket" thoi gian co do dai bang voi khung dang xet, dem
so log co cung signature trong moi bucket, roi lay trung binh + do lech
chuan tren cac bucket do. Day la dau vao cho anomaly_score.compute_anomaly_score().
"""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean, pstdev

from .clustering import compute_signature


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def bucket_key(ts: str, bucket_minutes: float) -> int:
    """Chi so bucket thoi gian (khung bucket_minutes phut) chua timestamp ts."""
    dt = _parse_ts(ts)
    epoch_minutes = dt.timestamp() / 60.0
    return int(epoch_minutes // bucket_minutes)


def historical_bucket_counts(
    history_logs: list[dict],
    service: str,
    signature: str,
    bucket_minutes: float,
    num_buckets: int,
    current_bucket: int,
) -> list[int]:
    """Dem so log co cung (service, signature) da cho trong moi bucket lich
    su (khong tinh bucket hien tai), tra ve danh sach do dai <= num_buckets,
    mot phan tu cho moi bucket lui ve truoc (bucket rong => 0, khong bi bo
    qua) de trung binh/do lech chuan phan anh dung muc do "im hoi lang
    tieng" giua cac lan xuat hien.

    Loc theo ca service (khong chi signature) de khop voi
    clustering.group_similar_errors() - 2 service cung signature phai co
    baseline rieng, khong tinh gop chung (xem docstring group_similar_errors).
    """
    counts: dict[int, int] = {}
    for log in history_logs:
        if log.get("service", "") != service or compute_signature(log) != signature:
            continue
        bucket = bucket_key(log["timestamp"], bucket_minutes)
        if bucket >= current_bucket:
            continue
        counts[bucket] = counts.get(bucket, 0) + 1

    return [counts.get(current_bucket - offset, 0) for offset in range(1, num_buckets + 1)]


def compute_baseline(history_counts: list[int]) -> dict:
    """Tra ve {"mean": ..., "stdev": ...} tu danh sach so luong theo bucket.

    Khong co lich su (list rong) => mean=0, stdev=0 (coi nhu chua co baseline,
    de anomaly_score xu ly nhu mot signature moi xuat hien).
    """
    if not history_counts:
        return {"mean": 0.0, "stdev": 0.0}
    return {
        "mean": mean(history_counts),
        "stdev": pstdev(history_counts) if len(history_counts) > 1 else 0.0,
    }


def now_bucket(bucket_minutes: float, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    return bucket_key(now.isoformat(), bucket_minutes)

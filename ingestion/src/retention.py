"""
Retention job - xoa log qua han.

File nay chi chua LOGIC xoa (run_retention). Lich chay dinh ky da duoc wire
san o 2 noi (xem ingestion/README.md muc "Retention"):
  - Mac dinh: APScheduler trong lifespan() cua ingestion/src/main.py, chay
    moi RETENTION_INTERVAL_HOURS gio (mac dinh 24h).
  - Thay the: scripts/run_retention.py, dung cho OS cron / k8s CronJob neu
    muon tach rieng khoi tien trinh FastAPI (dat RETENTION_INTERVAL_HOURS=0
    de tat scheduler trong tien trinh).

So ngay luu lay tu bien moi truong RETENTION_DAYS de khong hardcode theo
tung bien the ca nhan.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from .storage import LogStore

DEFAULT_RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "30"))


def run_retention(store: LogStore, retention_days: int = DEFAULT_RETENTION_DAYS) -> int:
    """Xoa moi log cu hon `retention_days` ngay. Tra ve so log da xoa."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    return store.delete_older_than(cutoff.isoformat())

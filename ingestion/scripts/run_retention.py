"""
Entry point retention cho OS-level cron / k8s CronJob (thay the cho scheduler
trong tien trinh FastAPI - xem `lifespan()` trong `ingestion/src/main.py`).

Dung khi muon tach retention ra khoi vong doi cua service (vd. scale rieng,
hoac chay 1 lan/ngay qua crontab thay vi giu scheduler song cung API).

Chay thu (tu thu muc goc repo, de import package `ingestion` hoat dong):
    RETENTION_DAYS=30 python -m ingestion.scripts.run_retention

Cau hinh qua bien moi truong, xem ingestion/README.md:
    RETENTION_DAYS, LOG_STORE_BACKEND, OPENSEARCH_URL, OPENSEARCH_INDEX, ...

Vi du crontab (chay luc 03:00 moi ngay):
    0 3 * * * cd /path/to/repo && RETENTION_DAYS=30 python -m ingestion.scripts.run_retention
"""

from __future__ import annotations

from ..src.retention import DEFAULT_RETENTION_DAYS, run_retention
from ..src.storage import get_store


def main() -> None:
    store = get_store()
    deleted = run_retention(store)
    print(f"[retention] deleted={deleted} retention_days={DEFAULT_RETENTION_DAYS}")


if __name__ == "__main__":
    main()

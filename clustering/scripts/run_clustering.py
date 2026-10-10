"""
Entry point clustering cho OS-level cron / k8s CronJob (thay the cho loop
vo han trong `src/main.py:run_forever()`).

Dung khi muon tach job clustering ra khoi mot tien trinh song (vd. scale
rieng, hoac chay dinh ky qua crontab thay vi giu mot process loop).

Chay thu (tu thu muc goc repo, de import package `clustering` hoat dong):
    python -m clustering.scripts.run_clustering

Cau hinh qua bien moi truong, xem clustering/README.md:
    CLUSTERING_WINDOW_MINUTES, CLUSTERING_BASELINE_WINDOWS, CLUSTERING_FETCH_SIZE,
    ANOMALY_THRESHOLD, ALERT_WEBHOOK_URL, CLUSTER_STORE_BACKEND, OPENSEARCH_URL, ...

Vi du crontab (chay moi 10 phut, khop voi CLUSTERING_WINDOW_MINUTES mac dinh):
    */10 * * * * cd /path/to/repo && python -m clustering.scripts.run_clustering
"""

from __future__ import annotations

from ..src.main import run_once


def main() -> None:
    results = run_once()
    alerted = sum(1 for r in results if r["status"] == "alerted")
    print(f"[clustering] clusters_computed={len(results)} alerted={alerted}")


if __name__ == "__main__":
    main()

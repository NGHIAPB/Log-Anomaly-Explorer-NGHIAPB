"""
Script evidence cho "Fault injection" (phu trach: Manh).

Goi lap lai /simulate-error cua demo-app trong mot khoang thoi gian xac dinh,
de tao ra mot "giai doan bat thuong" co kiem soat, kem timestamp bat dau/ket
thuc ro rang. Nam dung summary nay lam tham khao de tu gan nhan (ground-truth)
trong clustering/evaluation/labeled_incidents.json (file do Nam so huu, script
nay KHONG tu dong sua file do).

Chay thu (demo-app phai dang chay o port 8001):
    python -m demo_app.scripts.trigger_fault_window --duration 30 --rate 0.6 --fault-type error

Hoac truc tiep:
    cd demo-app
    python scripts/trigger_fault_window.py --duration 30 --rate 0.6 --fault-type error
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

import httpx


def run(base_url: str, duration_s: float, rate: float, fault_type: str, interval_s: float) -> dict:
    started_at = datetime.now(timezone.utc).isoformat()
    calls = 0
    faulted = 0
    status_counts: dict[str, int] = {}

    deadline = time.monotonic() + duration_s
    with httpx.Client(timeout=10.0) as client:
        while time.monotonic() < deadline:
            calls += 1
            try:
                resp = client.get(
                    f"{base_url}/simulate-error",
                    params={"rate": rate, "fault_type": fault_type},
                )
                status_counts[str(resp.status_code)] = status_counts.get(str(resp.status_code), 0) + 1
                if resp.status_code >= 400:
                    faulted += 1
            except httpx.HTTPError as exc:
                status_counts["request_error"] = status_counts.get("request_error", 0) + 1
                faulted += 1
                print(f"[trigger_fault_window] request error: {exc}")
            time.sleep(interval_s)

    ended_at = datetime.now(timezone.utc).isoformat()
    summary = {
        "service": "demo-web",
        "fault_type": fault_type,
        "rate": rate,
        "started_at": started_at,
        "ended_at": ended_at,
        "calls": calls,
        "faulted_calls": faulted,
        "status_counts": status_counts,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8001", help="URL cua demo-app")
    parser.add_argument("--duration", type=float, default=30.0, help="Thoi gian chay (giay)")
    parser.add_argument("--rate", type=float, default=0.5, help="Xac suat tiem loi moi lan goi")
    parser.add_argument(
        "--fault-type",
        default="error",
        choices=["error", "timeout", "bad_schema"],
        help="Loai fault injection",
    )
    parser.add_argument("--interval", type=float, default=0.5, help="Khoang nghi giua cac lan goi (giay)")
    args = parser.parse_args()

    summary = run(args.base_url, args.duration, args.rate, args.fault_type, args.interval)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

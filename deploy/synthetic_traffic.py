"""
Synthetic traffic generator - phan deploy cua Nghia.

Muc dich: giu dashboard/demo luon co du lieu "song" (khong phai du lieu cu/
trong) ma khong can ai thu cong goi curl/trigger_fault_window.py moi lan.
Chi goi vao cac endpoint CONG KHAI co san cua demo-app (/api/items,
/simulate-error) - KHONG sua code demo-app (Manh), khong tao them co che
sinh log nao trong demo-app ca.

Moi TICK_SECONDS (mac dinh 300s = 5 phut), chon ngau nhien 1 trong 5 kieu
hanh vi theo trong so - tao do da dang log (INFO/WARN/ERROR, quarantine,
anomaly, alert) thay vi lap lai mot khuon mau co dinh:

    normal (60%)    - 1 request GET /api/items (thinh thoang kem header
                       X-Client: mobile) -> 1 log INFO, dung lam baseline
    timeout (10%)   - 1 request /simulate-error?fault_type=timeout -> 1 log
                       WARN + request cham 3-6s (dung lam da dang level)
    quarantine (10%) - 1 request /simulate-error?fault_type=bad_schema -> 1
                       log SAI schema, test duong quarantine cua Ingestion
    anomaly (12%)   - burst ngan (5-12s) /simulate-error?fault_type=error,
                       rate/do dai NGAU NHIEN moi lan -> thuong du de
                       clustering thay bat thuong nhung CHUA CHAC vuot
                       ANOMALY_THRESHOLD
    alert (8%)      - burst manh hon (10-20s), rate cao hon -> nhieu kha
                       nang vuot ANOMALY_THRESHOLD -> status=alerted

QUAN TRONG - vi sao rate/do dai cua burst duoc NGAU NHIEN hoa moi lan (khong
dung so co dinh): baseline cua Nam tu thich nghi (xem docs/task/runbook.md
muc "Khi nhan duoc Alert") - neu lap lai DUNG MOT khuon mau burst nhieu lan,
z-score se giam dan toi khi he thong het con coi do la bat thuong. Ngau
nhien hoa cuong do giup van co alert that deu dan qua nhieu ngay thay vi
"tro" dan theo thoi gian.

Chay (dung trong docker-compose.yml o goc repo, service "synthetic-traffic"):
    python -m deploy.synthetic_traffic

Bien moi truong:
    DEMO_APP_URL            - mac dinh http://demo-app:8001 (ten service trong
                               mang Docker noi bo, xem docker-compose.yml)
    SYNTHETIC_TICK_SECONDS  - mac dinh 300 (5 phut)
"""

from __future__ import annotations

import os
import random
import time
from datetime import datetime, timezone

import httpx

DEMO_APP_URL = os.environ.get("DEMO_APP_URL", "http://demo-app:8001").rstrip("/")
TICK_SECONDS = float(os.environ.get("SYNTHETIC_TICK_SECONDS", "300"))

# (ten_tick, trong_so) - tong khong bat buoc = 100, chi can ty le tuong doi.
_TICK_WEIGHTS = [
    ("normal", 60),
    ("timeout", 10),
    ("quarantine", 10),
    ("anomaly", 12),
    ("alert", 8),
]


def _log(msg: str) -> None:
    # flush=True: chay nen, stdout bi buffer neu khong flush se khong thay
    # gi trong `docker logs` khi xem truc tiep.
    print(f"[synthetic-traffic] {datetime.now(timezone.utc).isoformat()} {msg}", flush=True)


def _headers() -> dict:
    # ~30% request dan sang luong mobile (service=demo-mobile-api) de da
    # dang hoa service, giong cach demo-app/README.md mo ta.
    return {"X-Client": "mobile"} if random.random() < 0.3 else {}


def _do_normal(client: httpx.Client) -> None:
    client.get(f"{DEMO_APP_URL}/api/items", headers=_headers(), timeout=10.0)


def _do_single_fault(client: httpx.Client, fault_type: str) -> None:
    client.get(
        f"{DEMO_APP_URL}/simulate-error",
        params={"rate": 1.0, "fault_type": fault_type},
        headers=_headers(),
        timeout=10.0,
    )


def _do_burst(client: httpx.Client, duration: float, rate: float) -> int:
    """Goi lap /simulate-error?fault_type=error trong `duration` giay. Tra
    ve so request da goi (de log lai, phuc vu quan sat/debug)."""
    calls = 0
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        try:
            client.get(
                f"{DEMO_APP_URL}/simulate-error",
                params={"rate": rate, "fault_type": "error"},
                headers=_headers(),
                timeout=10.0,
            )
        except httpx.HTTPError:
            pass  # job nen: 1 request loi khong duoc lam chet vong lap
        calls += 1
        time.sleep(0.3)
    return calls


def tick(client: httpx.Client) -> None:
    names, weights = zip(*_TICK_WEIGHTS)
    kind = random.choices(names, weights=weights, k=1)[0]

    if kind == "normal":
        _do_normal(client)
        _log("tick=normal -> 1 log INFO")
    elif kind == "timeout":
        _do_single_fault(client, "timeout")
        _log("tick=timeout -> 1 log WARN (request cham co chu dich)")
    elif kind == "quarantine":
        _do_single_fault(client, "bad_schema")
        _log("tick=quarantine -> 1 log sai schema (test duong quarantine)")
    elif kind == "anomaly":
        # Ngau nhien hoa de tranh baseline "hoc" mot khuon mau co dinh.
        duration = random.uniform(5, 12)
        rate = random.uniform(0.4, 0.6)
        calls = _do_burst(client, duration, rate)
        _log(f"tick=anomaly -> burst {duration:.1f}s rate={rate:.2f} ({calls} request)")
    else:  # alert
        duration = random.uniform(10, 20)
        rate = random.uniform(0.7, 0.95)
        calls = _do_burst(client, duration, rate)
        _log(f"tick=alert -> burst {duration:.1f}s rate={rate:.2f} ({calls} request)")


def main() -> None:
    _log(f"bat dau - DEMO_APP_URL={DEMO_APP_URL} TICK_SECONDS={TICK_SECONDS}")
    with httpx.Client() as client:
        while True:
            try:
                tick(client)
            except Exception as exc:  # job nen: 1 lan tick loi khong duoc lam chet vong lap
                _log(f"loi: {type(exc).__name__}: {exc}")
            time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    main()

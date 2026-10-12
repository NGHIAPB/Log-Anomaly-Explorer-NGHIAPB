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
    anomaly (12%)   - burst ngan (5-12s), fault_type NGAU NHIEN trong
                       {error, not_found, db_error} (3 signature khac nhau
                       hoan toan - xem demo-app/src/main.py), rate/do dai
                       cung ngau nhien moi lan -> thuong du de clustering
                       thay bat thuong nhung CHUA CHAC vuot ANOMALY_THRESHOLD
    alert (8%)      - burst manh hon (10-20s), fault_type ngau nhien nhu
                       tren, rate cao hon -> nhieu kha nang vuot
                       ANOMALY_THRESHOLD -> status=alerted

QUAN TRONG - vi sao rate/do dai/fault_type cua burst duoc NGAU NHIEN hoa moi
lan (khong dung mot khuon mau co dinh): baseline cua Nam tu thich nghi (xem
docs/task/runbook.md muc "Khi nhan duoc Alert") - neu lap lai DUNG MOT khuon
mau burst nhieu lan, z-score se giam dan toi khi he thong het con coi do la
bat thuong. Ngau nhien hoa (ca cuong do lan loai loi) giup van co alert that
deu dan qua nhieu ngay thay vi "tro" dan theo thoi gian, dong thoi tao ra
nhieu loai cum khac nhau tren dashboard thay vi mai mai chi 1 cum
"runtimeerror".

Chay nen (mac dinh, dung trong docker-compose.yml, service "synthetic-traffic"):
    python synthetic_traffic.py

Ban THU CONG 1 tick ngau nhien ngay lap tuc (khong doi 5 phut) - dung khi can
du lieu "song" gap de demo/kiem thu, chay song song voi container nen dang
chay binh thuong, khong xung dot:
    docker exec log-anomaly-synthetic-traffic python synthetic_traffic.py --once

Ban nhieu tick lien tiep (vd. 10 tick, cach nhau 3s) de nhanh chong co du
lieu da dang truoc khi demo:
    docker exec log-anomaly-synthetic-traffic python synthetic_traffic.py --count 10 --interval 3

Ep dung 1 kieu cu the (bo qua random trong so) - vd. muon chac chan co ngay
1 cum "alerted" de demo Incident View:
    docker exec log-anomaly-synthetic-traffic python synthetic_traffic.py --once --kind alert

Bien moi truong:
    DEMO_APP_URL            - mac dinh http://demo-app:8001 (ten service trong
                               mang Docker noi bo, xem docker-compose.yml)
    SYNTHETIC_TICK_SECONDS  - mac dinh 300 (5 phut) - chi dung cho che do chay nen
"""

from __future__ import annotations

import argparse
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


# 3 fault_type cua demo-app sinh log muc ERROR (co the vao cluster that) -
# khac voi "timeout" (WARN, khong vao cluster) va "bad_schema" (quarantine,
# khong vao index chinh). Random chon 1 trong 3 moi lan burst de dashboard
# co nhieu loai cum khac nhau thay vi mai mai chi "runtimeerror".
_ERROR_FAULT_TYPES = ["error", "not_found", "db_error"]


def _do_burst(client: httpx.Client, duration: float, rate: float, fault_type: str) -> int:
    """Goi lap /simulate-error?fault_type=<fault_type> trong `duration` giay.
    Tra ve so request da goi (de log lai, phuc vu quan sat/debug)."""
    calls = 0
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        try:
            client.get(
                f"{DEMO_APP_URL}/simulate-error",
                params={"rate": rate, "fault_type": fault_type},
                headers=_headers(),
                timeout=10.0,
            )
        except httpx.HTTPError:
            pass  # job nen: 1 request loi khong duoc lam chet vong lap
        calls += 1
        time.sleep(0.3)
    return calls


_TICK_KINDS = [name for name, _ in _TICK_WEIGHTS]


def tick(client: httpx.Client, forced_kind: str | None = None) -> None:
    if forced_kind is not None:
        kind = forced_kind
    else:
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
        # Ngau nhien hoa ca fault_type lan rate/do dai, de tranh baseline
        # "hoc" mot khuon mau co dinh VA de co nhieu loai cum khac nhau.
        duration = random.uniform(5, 12)
        rate = random.uniform(0.4, 0.6)
        fault_type = random.choice(_ERROR_FAULT_TYPES)
        calls = _do_burst(client, duration, rate, fault_type)
        _log(f"tick=anomaly fault_type={fault_type} -> burst {duration:.1f}s rate={rate:.2f} ({calls} request)")
    else:  # alert
        duration = random.uniform(10, 20)
        rate = random.uniform(0.7, 0.95)
        fault_type = random.choice(_ERROR_FAULT_TYPES)
        calls = _do_burst(client, duration, rate, fault_type)
        _log(f"tick=alert fault_type={fault_type} -> burst {duration:.1f}s rate={rate:.2f} ({calls} request)")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--once", action="store_true",
        help="Chay dung 1 tick ngay lap tuc roi thoat (thay vi vong lap nen vo han)",
    )
    parser.add_argument(
        "--count", type=int, default=None,
        help="Chay N tick lien tiep roi thoat (vd. --count 10 de nhanh chong co du lieu da dang)",
    )
    parser.add_argument(
        "--interval", type=float, default=3.0,
        help="So giay nghi giua cac tick khi dung --count (mac dinh 3s, KHONG dung TICK_SECONDS cua che do nen)",
    )
    parser.add_argument(
        "--kind", choices=_TICK_KINDS, default=None,
        help="Ep dung 1 kieu tick cu the thay vi chon ngau nhien theo trong so (vd. --kind alert)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.once or args.count is not None:
        # Che do thu cong: chay 1 hoac N tick roi thoat, KHONG vao vong lap
        # nen vo han. Dung song song voi container dang chay binh thuong qua
        # `docker exec` - khong xung dot vi httpx khong giu state gi chung.
        n = args.count if args.count is not None else 1
        _log(f"che do thu cong: {n} tick, interval={args.interval}s, kind={args.kind or 'ngau nhien'}")
        with httpx.Client() as client:
            for i in range(n):
                try:
                    tick(client, forced_kind=args.kind)
                except Exception as exc:
                    _log(f"loi: {type(exc).__name__}: {exc}")
                if i < n - 1:
                    time.sleep(args.interval)
        _log("xong che do thu cong")
        return

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

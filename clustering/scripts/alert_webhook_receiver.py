"""
Webhook receiver toi gian de KIEM CHUNG alert that su duoc gui di.

Vi sao can: `ALERT_WEBHOOK_URL` mac dinh rong -> `check_and_alert()` chi cap
nhat status="alerted" chu KHONG gui gi (xem src/alert.py). Script nay dung
mot HTTP server nho de nhan va in ra payload that, chung minh duong alert
chay day du dau-cuoi (phat hien -> gui -> nguoi van hanh nhan duoc), thay vi
chi chung minh duoc nua dau.

Chi dung cho dev/test/evidence - KHONG phai thanh phan chay that cua he thong
(production dung webhook that: Slack, Discord, email gateway, ...).

Chay (khong can thu vien ngoai, chi stdlib):
    python -m clustering.scripts.alert_webhook_receiver            # cong 9099
    python -m clustering.scripts.alert_webhook_receiver --port 8888

Roi tro ALERT_WEBHOOK_URL vao no. Vi du khi clustering chay trong Docker
(docker-compose.yml o goc repo) con receiver chay tren may host:

    # .env o goc repo
    ALERT_WEBHOOK_URL=http://host.docker.internal:9099/alert

    docker compose up -d
    python demo-app/scripts/trigger_fault_window.py --duration 15 --rate 0.9 --interval 0.05

Payload nhan duoc phai dung hop dong trong docs/architect/contracts/api-contract.md
muc "Alert": {cluster_id, score, service, first_seen}.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer


class _AlertHandler(BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802 (ten do BaseHTTPRequestHandler quy dinh)
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"_raw_khong_phai_json": raw}

        record = {"received_at": datetime.now(timezone.utc).isoformat(), "payload": payload}
        _AlertHandler.received.append(record)

        # flush=True: khi chay nen va redirect stdout ra file, Python buffer
        # theo block nen khong flush se khong thay gi trong file log.
        print(f"\n=== ALERT #{len(_AlertHandler.received)} nhan duoc ===", flush=True)
        print(json.dumps(record, indent=2, ensure_ascii=False), flush=True)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *args) -> None:
        """Tat log mac dinh cua http.server - chi in payload alert cho de doc."""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9099)
    args = parser.parse_args()

    server = HTTPServer(("0.0.0.0", args.port), _AlertHandler)
    print(f"[alert-receiver] dang nghe tren http://0.0.0.0:{args.port} (Ctrl+C de dung)", flush=True)
    print(
        f"[alert-receiver] dat ALERT_WEBHOOK_URL=http://host.docker.internal:{args.port}/alert"
        " neu clustering chay trong Docker",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n[alert-receiver] da nhan tong cong {len(_AlertHandler.received)} alert", flush=True)


if __name__ == "__main__":
    main()

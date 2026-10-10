"""
Danh gia Precision / Recall cua clustering + anomaly score, dua tren labeled_incidents.json.

GitHub evidence: "precision/recall". Chay sau khi da co du lieu that + labeled_incidents.json
duoc dien day du (xem README.md va evaluation/labeled_incidents.json).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

_LABELED_PATH = Path(__file__).resolve().parent / "labeled_incidents.json"


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _windows_overlap(a_from: str, a_to: str, b_from: str, b_to: str) -> bool:
    return _parse_ts(a_from) <= _parse_ts(b_to) and _parse_ts(b_from) <= _parse_ts(a_to)


def _cluster_overlaps_incident(cluster: dict, incident: dict) -> bool:
    """Mot cluster duoc coi la khop voi incident da gan nhan khi: cung
    service, cung signature (loi duoc nhom dung), VA khung thoi gian cua
    cluster (first_seen..last_seen) chong lap voi khung cua incident
    (window_from..window_to) - tranh truong hop trung signature/service
    "ngau nhien" o nhung thoi diem khong lien quan.
    """
    if cluster.get("signature") != incident.get("expected_cluster_signature"):
        return False
    if cluster.get("service") != incident.get("service"):
        return False
    return _windows_overlap(
        cluster.get("first_seen", ""),
        cluster.get("last_seen", ""),
        incident.get("window_from", ""),
        incident.get("window_to", ""),
    )


def evaluate(predicted_clusters: list[dict], labeled_path: Path = _LABELED_PATH) -> dict:
    """predicted_clusters: danh sach cluster co status == 'alerted' (he thong da bao),
    kem truong "service" noi bo (xem anomaly_score.compute_anomaly_score / main.run_once -
    KHONG phai ban ghi da "lam sach" theo cluster-record.schema.json).

    Tra ve {"precision": float, "recall": float, "true_positive": int,
            "false_positive": int, "false_negative": int}
    """
    incidents = json.loads(labeled_path.read_text(encoding="utf-8"))["incidents"]

    matched_incidents = set()
    true_positive = 0
    for cluster in predicted_clusters:
        hit = False
        for incident in incidents:
            if _cluster_overlaps_incident(cluster, incident):
                matched_incidents.add(incident["incident_id"])
                hit = True
        if hit:
            true_positive += 1

    false_positive = len(predicted_clusters) - true_positive
    false_negative = len(incidents) - len(matched_incidents)

    precision = true_positive / len(predicted_clusters) if predicted_clusters else 0.0
    recall = len(matched_incidents) / len(incidents) if incidents else 0.0

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
    }


def _with_service(cluster: dict) -> dict:
    """ClusterRecord doc trong ClusterStore khong co truong "service" (khong
    nam trong cluster-record.schema.json - xem storage.to_cluster_record()).
    De so khop voi incident da gan nhan (co "service"), tra lai service tu
    log goc qua log_ids - dung chinh LogStore cua Ingestion, giong cach
    Incident View (Nghia) se tra cuu log tu log_ids.
    """
    if cluster.get("service") or not cluster.get("log_ids"):
        return cluster
    from ingestion.src.storage import get_store

    logs = get_store().get_by_ids(cluster["log_ids"][:1])
    service = logs[0].get("service", "") if logs else ""
    return {**cluster, "service": service}


if __name__ == "__main__":
    from clustering.src.storage import get_cluster_store

    alerted = [_with_service(c) for c in get_cluster_store().list_clusters(status="alerted", size=1000)]
    print(evaluate(predicted_clusters=alerted))

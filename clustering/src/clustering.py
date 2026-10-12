"""
Nhom cac loi tuong tu (clustering).

Chuan hoa message truoc khi nhom, de cac loi cung "hinh dang" nhung khac
gia tri cu the (id, so luong, uuid, dia chi...) duoc nhom chung. Vi du:
"User 123 not found" va "User 456 not found" deu chuan hoa thanh
"User <num> not found" -> cung mot signature.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE
)
_HEX_ID_RE = re.compile(r"\b0x[0-9a-f]+\b|\b[0-9a-f]{12,}\b", re.IGNORECASE)
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
_QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"")
_WS_RE = re.compile(r"\s+")


def normalize_message(message: str) -> str:
    """Thay the cac phan 'bien thien' (id, so, uuid, chuoi trong quote) bang
    token co dinh, giu lai 'hinh dang' chung cua message de nhom dung loi
    tuong tu co gia tri khac nhau.
    """
    text = message or ""
    text = _UUID_RE.sub("<uuid>", text)
    text = _HEX_ID_RE.sub("<id>", text)
    text = _QUOTED_RE.sub("<val>", text)
    text = _NUM_RE.sub("<num>", text)
    text = _WS_RE.sub(" ", text).strip().lower()
    return text


def compute_signature(log: dict) -> str:
    """Dac trung dung de nhom mot log loi.

    Uu tien `stack_trace` (dong dau tien, neu co) vi stack trace thuong on
    dinh hon message khi cung mot loai loi xay ra nhieu lan voi tham so khac
    nhau; fallback ve message da chuan hoa khi khong co stack_trace.
    """
    stack_trace = log.get("stack_trace")
    if stack_trace:
        first_line = stack_trace.strip().splitlines()[-1] if stack_trace.strip() else ""
        if first_line:
            return normalize_message(first_line)
    return normalize_message(log.get("message", ""))


def group_similar_errors(logs: Iterable[dict]) -> dict[tuple[str, str], list[dict]]:
    """Nhom danh sach log (chi nhung log level ERROR/FATAL) theo CAP
    (service, signature) - khong chi signature don thuan.

    Vi sao can ca service: 2 service khac nhau co the sinh ra loi CUNG
    signature (vd. demo-web va demo-mobile-api cung goi chung 1 ham loi
    "Simulated downstream failure" trong demo-app). Neu chi nhom theo
    signature, ca 2 service bi gop chung vao 1 nhom, va
    anomaly_score.compute_anomaly_score() (lay service tu logs[0]) se gan
    ClusterRecord cho MOT service duy nhat mot cach khong on dinh (phu
    thuoc thu tu log nao dung dau danh sach o moi lan chay) - cac log con
    lai cua service kia bi "nuot" vao nham cum, con service kia khong bao
    gio duoc cap nhat du van co loi moi that su xay ra.

    Tra ve: { (service, signature): [log, log, ...] }
    Day la dau vao cho anomaly_score.compute_anomaly_score().
    """
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for log in logs:
        if log.get("level") not in ("ERROR", "FATAL"):
            continue
        key = (log.get("service", ""), compute_signature(log))
        groups[key].append(log)
    return dict(groups)

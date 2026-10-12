"""Test cho ingestion/src/validator.py - diem dam bao hop dong du lieu
giua demo-app (Manh) va ingestion (Minh), xem log-schema.json."""

from __future__ import annotations

from ingestion.src.validator import validate_log

VALID_LOG = {
    "timestamp": "2026-10-12T09:00:00Z",
    "level": "ERROR",
    "service": "demo-web",
    "trace_id": "abc123",
    "span_id": "span1",
    "message": "Simulated downstream failure",
}


def test_log_hop_le_khong_co_loi():
    assert validate_log(VALID_LOG) == []


def test_log_hop_le_voi_truong_tuy_chon():
    log = {**VALID_LOG, "stack_trace": "Traceback...", "metadata": {"http.status_code": 500}}
    assert validate_log(log) == []


def test_thieu_truong_bat_buoc():
    log = {k: v for k, v in VALID_LOG.items() if k != "trace_id"}
    errors = validate_log(log)
    assert errors  # phai co loi
    assert any("trace_id" in e for e in errors)


def test_level_ngoai_enum():
    log = {**VALID_LOG, "level": "CRITICAL"}  # khong nam trong enum hop le
    errors = validate_log(log)
    assert errors
    assert any("level" in e for e in errors)


def test_truong_khong_duoc_phep_additionalProperties_false():
    log = {**VALID_LOG, "unknown_field": "khong duoc phep"}
    errors = validate_log(log)
    assert errors


def test_timestamp_sai_dinh_dang_HIEN_CHUA_BI_BAT():
    # GAP DA PHAT HIEN (2026-10-12, qua chinh test nay): Draft7Validator duoc
    # khoi tao KHONG kem FormatChecker (xem validator.py: "Draft7Validator(_schema)"),
    # nen rang buoc "format": "date-time" cua timestamp trong log-schema.json
    # hien KHONG duoc kiem tra that su - 1 chuoi bat ky van "hop le". Test
    # nay ghi lai dung HANH VI HIEN TAI (khong phai hanh vi dung theo
    # schema), de neu sau nay co fix (truyen format_checker=Draft7Validator.FORMAT_CHECKER)
    # thi test se do bao dau de cap nhat, chu khong lang le bo sot.
    log = {**VALID_LOG, "timestamp": "khong-phai-ngay-thang"}
    errors = validate_log(log)
    assert errors == []

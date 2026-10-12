"""Test cho clustering/src/clustering.py - phan "nhom loi tuong tu", lo gic
thuat toan quan trong nhat can bao ve (truoc gio chua co test tu dong nao)."""

from __future__ import annotations

from clustering.src.clustering import compute_signature, group_similar_errors, normalize_message


class TestNormalizeMessage:
    def test_chuan_hoa_so(self):
        assert normalize_message("User 123 not found") == normalize_message("User 456 not found")
        assert normalize_message("User 123 not found") == "user <num> not found"

    def test_chuan_hoa_uuid(self):
        msg1 = "Request abc12345-1234-5678-9abc-123456789012 failed"
        msg2 = "Request ffffffff-1234-5678-9abc-fedcba987654 failed"
        assert normalize_message(msg1) == normalize_message(msg2)
        assert "<uuid>" in normalize_message(msg1)

    def test_chuan_hoa_chuoi_trong_quote(self):
        assert normalize_message("Field 'email' is invalid") == normalize_message("Field 'username' is invalid")

    def test_chuan_hoa_khong_phan_biet_hoa_thuong(self):
        assert normalize_message("User Not Found") == normalize_message("user not found")

    def test_message_rong(self):
        assert normalize_message("") == ""
        assert normalize_message(None) == ""  # type: ignore[arg-type]


class TestComputeSignature:
    def test_uu_tien_dong_cuoi_stack_trace_khi_co(self):
        log = {
            "message": "khac voi stack trace",
            "stack_trace": "Traceback (most recent call last):\n  File x\nRuntimeError: Simulated downstream failure",
        }
        assert compute_signature(log) == "runtimeerror: simulated downstream failure"

    def test_fallback_ve_message_khi_khong_co_stack_trace(self):
        log = {"message": "Simulated downstream failure"}
        assert compute_signature(log) == "simulated downstream failure"

    def test_stack_trace_rong_fallback_ve_message(self):
        log = {"message": "loi don gian", "stack_trace": ""}
        assert compute_signature(log) == "loi don gian"

    def test_2_user_id_khac_nhau_cung_signature(self):
        log1 = {"message": "User 1000 not found", "stack_trace": "ValueError: User 1000 not found"}
        log2 = {"message": "User 9999 not found", "stack_trace": "ValueError: User 9999 not found"}
        assert compute_signature(log1) == compute_signature(log2)


class TestGroupSimilarErrors:
    def test_chi_lay_log_error_va_fatal(self):
        logs = [
            {"level": "INFO", "service": "demo-web", "message": "ok"},
            {"level": "WARN", "service": "demo-web", "message": "cham"},
            {"level": "ERROR", "service": "demo-web", "message": "loi 1"},
            {"level": "FATAL", "service": "demo-web", "message": "loi 2"},
        ]
        groups = group_similar_errors(logs)
        total_logs = sum(len(v) for v in groups.values())
        assert total_logs == 2

    def test_nhom_theo_cap_service_signature_khong_chi_signature(self):
        """Day chinh la fix da lam (2026-10-12): 2 service cung signature
        PHAI tach thanh 2 nhom rieng, khong gop chung (xem clustering/README.md
        muc "Bug that da sua")."""
        logs = [
            {"level": "ERROR", "service": "demo-web", "message": "Simulated downstream failure"},
            {"level": "ERROR", "service": "demo-web", "message": "Simulated downstream failure"},
            {"level": "ERROR", "service": "demo-mobile-api", "message": "Simulated downstream failure"},
        ]
        groups = group_similar_errors(logs)
        assert len(groups) == 2
        assert len(groups[("demo-web", "simulated downstream failure")]) == 2
        assert len(groups[("demo-mobile-api", "simulated downstream failure")]) == 1

    def test_2_signature_khac_nhau_tach_rieng(self):
        logs = [
            {"level": "ERROR", "service": "demo-web", "message": "Simulated downstream failure"},
            {"level": "ERROR", "service": "demo-web", "message": "Database connection pool exhausted"},
        ]
        groups = group_similar_errors(logs)
        assert len(groups) == 2

    def test_danh_sach_rong_tra_ve_dict_rong(self):
        assert group_similar_errors([]) == {}

"""Test cho demo-app/src/main.py (FastAPI) - dung TestClient, khong goi mang
that: monkeypatch `httpx.post` cua module main de khong phu thuoc Ingestion
dang chay (emit_log() da duoc thiet ke nuot httpx.HTTPError, nhung goi mang
thuc trong test se cham/khong on dinh tuy moi truong, nen gia lap thay vi
dua vao hanh vi "fail im lang" do)."""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

main = importlib.import_module("demo-app.src.main")
client = TestClient(main.app)


@pytest.fixture(autouse=True)
def _fake_httpx_post(monkeypatch):
    """Chan mang thuc, ghi lai cac payload da "gui" de assert noi dung log."""
    calls: list[dict] = []

    def fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json})

    monkeypatch.setattr(main.httpx, "post", fake_post)
    return calls


class TestHealth:
    def test_health_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "service": "demo-web"}


class TestListItems:
    def test_mac_dinh_service_demo_web(self, _fake_httpx_post):
        resp = client.get("/api/items")
        assert resp.status_code == 200
        body = resp.json()
        assert body["service"] == "demo-web"
        assert body["items"] == ["item-1", "item-2", "item-3"]
        assert _fake_httpx_post[0]["json"]["service"] == "demo-web"

    def test_header_x_client_mobile_doi_service(self, _fake_httpx_post):
        resp = client.get("/api/items", headers={"X-Client": "mobile"})
        body = resp.json()
        assert body["service"] == "demo-mobile-api"
        assert _fake_httpx_post[0]["json"]["service"] == "demo-mobile-api"

    def test_header_x_client_khong_phan_biet_hoa_thuong(self, _fake_httpx_post):
        resp = client.get("/api/items", headers={"X-Client": "MOBILE"})
        assert resp.json()["service"] == "demo-mobile-api"


class TestSimulateError:
    def test_rate_0_luon_thanh_cong(self, _fake_httpx_post):
        resp = client.get("/simulate-error", params={"rate": 0.0})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_fault_type_error_mac_dinh_tra_500(self, _fake_httpx_post):
        resp = client.get("/simulate-error", params={"rate": 1.0})
        assert resp.status_code == 500
        assert "Simulated downstream failure" in resp.json()["detail"]
        sent = _fake_httpx_post[0]["json"]
        assert sent["level"] == "ERROR"
        assert sent["stack_trace"] is not None

    def test_fault_type_timeout_tra_504(self, _fake_httpx_post):
        resp = client.get("/simulate-error", params={"rate": 1.0, "fault_type": "timeout"})
        assert resp.status_code == 504

    def test_fault_type_bad_schema_tra_502_va_gui_log_sai_schema(self, _fake_httpx_post):
        resp = client.get("/simulate-error", params={"rate": 1.0, "fault_type": "bad_schema"})
        assert resp.status_code == 502
        sent = _fake_httpx_post[0]["json"]
        assert sent["level"] == "CRITICAL"  # khong nam trong enum hop le, co chu dich
        assert "trace_id" not in sent  # thieu truong bat buoc, co chu dich

    def test_fault_type_not_found_tra_404_voi_user_id_ngau_nhien(self, _fake_httpx_post):
        resp = client.get("/simulate-error", params={"rate": 1.0, "fault_type": "not_found"})
        assert resp.status_code == 404
        assert "User" in resp.json()["detail"]
        assert "not found" in resp.json()["detail"]
        sent = _fake_httpx_post[0]["json"]
        assert sent["level"] == "ERROR"
        assert "ValueError" in sent["stack_trace"]

    def test_fault_type_db_error_tra_503(self, _fake_httpx_post):
        resp = client.get("/simulate-error", params={"rate": 1.0, "fault_type": "db_error"})
        assert resp.status_code == 503
        sent = _fake_httpx_post[0]["json"]
        assert sent["message"] == "Database connection pool exhausted"
        assert "ConnectionError" in sent["stack_trace"]

    def test_fault_type_khong_hop_le_tra_400(self, _fake_httpx_post):
        resp = client.get("/simulate-error", params={"rate": 1.0, "fault_type": "khong-ton-tai"})
        assert resp.status_code == 400
        assert "Unknown fault_type" in resp.json()["detail"]

    def test_fault_type_mobile_header_giu_dung_service(self, _fake_httpx_post):
        resp = client.get(
            "/simulate-error",
            params={"rate": 1.0, "fault_type": "db_error"},
            headers={"X-Client": "mobile"},
        )
        assert resp.status_code == 503
        assert _fake_httpx_post[0]["json"]["service"] == "demo-mobile-api"

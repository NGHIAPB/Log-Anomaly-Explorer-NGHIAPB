# demo-app — Mạnh

Ứng dụng demo (web, giả lập mobile qua API) đóng vai trò **nguồn log** cho Log Anomaly Explorer. Không phải sản phẩm chính — chỉ cần đủ để sinh structured log + trace thật và tạo được bất thường có kiểm soát.

## Trách nhiệm

- [x] Gắn OpenTelemetry SDK (`src/telemetry.py`) — `TracerProvider` thật + exporter (OTLP nếu có `OTEL_EXPORTER_OTLP_ENDPOINT`, fallback console), sinh `trace_id`/`span_id` thật cho mỗi request qua middleware tracing trong `src/main.py`
- [x] Hoàn thiện `emit_log()` trong `src/main.py` để dùng trace context thật thay vì placeholder
- [x] Thêm endpoint giả lập cho luồng mobile — gọi `/api/items` kèm header `X-Client: mobile` → log được gán `service=demo-mobile-api` thay vì `demo-web`
- [x] Mở rộng `/simulate-error` với tham số `fault_type` (`error`, `timeout`, `bad_schema`, `not_found`, `db_error`) để phong phú dữ liệu fault injection

## Hợp đồng đang tuân theo

Mọi log gửi đi qua `POST {INGESTION_URL}/ingest` phải đúng [`log-schema.json`](../docs/architect/contracts/log-schema.json).

## Chạy thử

```bash
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8001
```

- `GET /health` — kiểm tra service đang chạy
- `GET /api/items` — sinh log INFO bình thường (baseline, `service=demo-web`)
- `GET /api/items` kèm header `X-Client: mobile` — baseline cho luồng mobile (`service=demo-mobile-api`)

  Đã kiểm chứng trên bản deploy thật (2026-10-12): gọi 12 request baseline + 10 request
  `/simulate-error` kèm header `X-Client: mobile` → sinh ra **22 log thật** mang
  `service=demo-mobile-api` (gồm cả INFO lẫn ERROR), xác nhận qua
  `GET /search?service=demo-mobile-api`. Nhờ vậy nhánh "Mobile" trong sơ đồ kiến trúc
  (`docs/architect/architecture-sod.png`) có dữ liệu thật, và bộ lọc theo `service` trên UI
  có ít nhất 2 service để phân biệt.
  ```bash
  curl -H "X-Client: mobile" "<BASE_URL>/demo/api/items"
  curl -H "X-Client: mobile" "<BASE_URL>/demo/simulate-error?rate=1.0"
  ```
- `GET /simulate-error?rate=0.3&fault_type=error` — tiêm lỗi có xác suất `rate`, dùng để tạo giai đoạn bất thường có kiểm soát

### Trace thật (OpenTelemetry)

Mỗi request được bọc trong một span (middleware `tracing_middleware` trong `src/main.py`). `trace_id`/`span_id` của span đó được gắn vào mọi structured log gửi về Ingestion qua `emit_log()`. Mặc định (không cấu hình `OTEL_EXPORTER_OTLP_ENDPOINT`) span được in ra console để tiện quan sát khi demo local không có collector; nếu có collector OTLP/HTTP, set biến môi trường này để xuất span thật về đó.

## Evidence sở hữu — Fault injection

**Cách bật/tắt:** fault injection nằm ở endpoint `GET /simulate-error`, mặc định tắt khi không gọi tới (các endpoint baseline như `/api/items` không bao giờ tiêm lỗi).

**Tham số điều khiển:**
- `rate` (0.0–1.0): xác suất tiêm lỗi mỗi lần gọi. `rate=0` = không lỗi, `rate=1` = luôn lỗi.
- `fault_type`:
  - `error` (mặc định) — lỗi 500 ngẫu nhiên ở tầng ứng dụng (`RuntimeError`), log `ERROR` kèm `stack_trace`.
  - `timeout` — giả lập downstream chậm (delay 3–6s), trả về `504`, log `WARN` trước khi delay.
  - `bad_schema` — gửi thẳng một log **sai** `log-schema.json` (thiếu `trace_id`/`span_id`, `level` ngoài enum) về Ingestion để kiểm tra cơ chế quarantine, trả về `502`.
  - `not_found` — lỗi nghiệp vụ (`ValueError: User <id> not found`, id ngẫu nhiên mỗi lần), log `ERROR` kèm `stack_trace`, trả về `404`. Signature khác hẳn `error` — đồng thời minh hoạ `clustering.normalize_message()` (Nam) chuẩn hoá đúng các lỗi cùng "hình dạng" nhưng khác giá trị số.
  - `db_error` — lỗi tầng hạ tầng (`ConnectionError: Database connection pool exhausted`), log `ERROR` kèm `stack_trace`, trả về `503`. Signature khác cả `error` lẫn `not_found` — tạo thêm cụm lỗi thật thứ 3 trong hệ thống, không chỉ 1 loại lỗi lặp lại ở nhiều service.

**Log/script tạo giai đoạn bất thường:** [`scripts/trigger_fault_window.py`](scripts/trigger_fault_window.py) — gọi lặp `/simulate-error` trong một khoảng thời gian cố định, in ra JSON summary gồm `started_at`/`ended_at` (UTC), `fault_type`, `rate`, số lần gọi, số lần lỗi. Ví dụ:

```bash
cd demo-app
python scripts/trigger_fault_window.py --duration 30 --rate 0.6 --fault-type error
```

Khoảng `[started_at, ended_at]` in ra từ script này là đầu vào để Nam gán nhãn ground-truth trong `clustering/evaluation/labeled_incidents.json` (file đó do Nam sở hữu, script này không tự sửa).

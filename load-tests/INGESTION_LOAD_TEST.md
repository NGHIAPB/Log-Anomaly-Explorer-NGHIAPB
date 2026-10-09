# Load test — Ingestion (Minh)

Evidence GitHub bắt buộc "Load test (ingestion)" — xem `README.md` gốc, mục GitHub evidence.

## Cách chạy

```bash
# 1. OpenSearch that (khong co Docker: LOG_STORE_BACKEND=memory khi chay uvicorn ben duoi)
docker compose -f ingestion/docker-compose.yml up -d

# 2. Ingestion service
cd ingestion && pip install -r requirements.txt
uvicorn src.main:app --port 8000

# 3. Load test (chi IngestionUser - khong dung chung QueryUser cua Nghia)
cd load-tests
locust -f locustfile.py IngestionUser --headless --host http://localhost:8000 \
  --users 50 --spawn-rate 10 --run-time 30s \
  --csv ingestion_load_test --html ingestion_load_test_report.html
```

## Kết quả đo được (2026-10-09)

Môi trường: OpenSearch 2.17.0 single-node (Docker, dev), Ingestion chạy local
bằng Uvicorn (1 worker), 50 user đồng thời, spawn-rate 10 user/s, 30 giây,
payload theo `_valid_log_payload()` (90%) + `_malformed_log_payload()` (10%,
test đường quarantine).

| Chỉ số | Giá trị |
|---|---|
| Tổng số request | 3 797 |
| Throughput trung bình | ~127 req/s (đỉnh ~147 req/s) |
| Tỷ lệ lỗi | 0.00% (kể cả nhánh quarantine, vì request trả đúng `400` được tính là success — xem `catch_response` trong `locustfile.py`) |
| Latency P50 | 47 ms |
| Latency P95 | 57 ms |
| Latency P99 | 62 ms (một số ít request ở giây đầu tiên spawn đồng loạt lên tới ~2.1s — nghi do lần flush/segment đầu tiên của OpenSearch; từ giây thứ 2 trở đi latency ổn định quanh P95 ~57ms) |
| Số log hợp lệ đã ghi (`logs`) | 3 418 |
| Số log quarantine (`logs-quarantine`) | 380 (~10%, đúng tỷ lệ payload lỗi chủ ý gửi) |

Chi tiết đầy đủ: `ingestion_load_test_stats.csv`, `ingestion_load_test_stats_history.csv`,
`ingestion_load_test_report.html`.

## Ghi chú kỹ thuật quan trọng rút ra từ load test

- Lần chạy đầu tiên dùng `refresh=True` trên mỗi lần ghi index (để search thấy
  log ngay lập tức khi test thủ công) khiến P95 tăng lên ~130ms và P99 ~2.1s
  do tranh chấp refresh liên tục trên một node OpenSearch. Đã đổi sang để
  OpenSearch tự refresh near-real-time (mặc định ~1s/lần, xem `storage.py`),
  giảm P95 xuống còn ~57ms mà không ảnh hưởng tới yêu cầu nghiệp vụ (search và
  clustering đều không cần tính nhất quán tức thời theo mili-giây).
- `write_log`/`write_quarantine` không force refresh nữa — nếu cần test thủ
  công bằng `curl` rồi `search` ngay (<1s sau), có thể thấy độ trễ nhỏ do đây
  là đánh đổi đã chọn có chủ đích cho throughput.

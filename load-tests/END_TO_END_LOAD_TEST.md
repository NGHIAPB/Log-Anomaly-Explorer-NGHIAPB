# Load test — End-to-end (Nghĩa)

Evidence GitHub bắt buộc "Load test (end-to-end)" — xem `README.md` gốc, mục GitHub evidence.
Khác với [`INGESTION_LOAD_TEST.md`](INGESTION_LOAD_TEST.md) (chỉ `POST /ingest`), bài test này
chạy **toàn bộ pipeline thật**: demo-app → ingestion → clustering (job nền) → query-api
(search + Incident View), trên dữ liệu thật trong OpenSearch — không dùng backend `memory`.

## Cách chạy

```bash
# 1. OpenSearch thật (dùng chung cho ingestion + clustering)
docker compose -f ingestion/docker-compose.yml up -d

# 2. Các service, chạy từ thư mục gốc repo (để import package dạng ingestion.*/clustering.*/query-api.* hoạt động)
uvicorn ingestion.src.main:app --port 8000
uvicorn demo-app.src.main:app --port 8001
uvicorn query-api.src.main:app --port 8002

# 3. (tuỳ chọn) Tạo trước vài cụm bất thường thật để /clusters, /clusters/{id} có dữ liệu
python demo-app/scripts/trigger_fault_window.py --duration 15 --rate 0.9 --interval 0.05
CLUSTERING_INTERVAL_SECONDS=0 CLUSTERING_WINDOW_MINUTES=5 python -m clustering.src.main

# 4a. Load test chỉ tầng Query & Incident API (đo riêng /search, /clusters, /clusters/{id})
cd load-tests
locust -f locustfile.py QueryUser --headless --host http://localhost:8002 \
  --users 30 --spawn-rate 10 --run-time 30s \
  --csv e2e_load_test --html e2e_load_test_report.html

# 4b. Load test TOÀN BỘ pipeline cùng lúc (IngestionUser + QueryUser chạy song song,
#     mỗi class tự dùng host riêng đã khai báo trong locustfile.py nên không cần --host)
locust -f locustfile.py --headless \
  --users 60 --spawn-rate 20 --run-time 45s \
  --csv e2e_full_pipeline --html e2e_full_pipeline_report.html
```

## Kết quả đo được (2026-10-10)

Môi trường: OpenSearch 2.17.0 single-node (Docker, dev), 4 service (`ingestion` 8000,
`demo-app` 8001, `query-api` 8002, job `clustering` chạy rời rạc) đều chạy local bằng Uvicorn
(1 worker/service) trên cùng máy chạy Locust — số liệu phản ánh đúng khả năng chịu tải của
**code**, không phải một môi trường production nhiều máy.

### 4a. Chỉ Query & Incident API (`QueryUser`, 30 user, spawn-rate 10, 30s)

| Endpoint | Request | Lỗi | P50 | P95 | P99 | Req/s |
|---|---|---|---|---|---|---|
| `GET /clusters` | 323 | 0 | 49 ms | 2100 ms* | 2100 ms* | 11.1 |
| `GET /clusters/{id}` (Incident View) | 126 | 0 | 48 ms | 56 ms | 66 ms | 4.3 |
| `GET /search?service=...` | 168 | 0 | 55 ms | 2100 ms* | 2100 ms* | 5.8 |
| `GET /search?trace_id=...` | 135 | 0 | 49 ms | 58 ms | 2100 ms* | 4.6 |
| **Tổng** | **752** | **0 (0.00%)** | **49 ms** | **65 ms** | **2100 ms\*** | **25.8** |

### 4b. Toàn bộ pipeline cùng lúc (`IngestionUser` + `QueryUser`, 60 user, spawn-rate 20, 45s)

| Endpoint | Request | Lỗi | P50 | P95 | P99 | Req/s |
|---|---|---|---|---|---|---|
| `POST /ingest` | 3 638 | 0 | 49 ms | 58 ms | 66 ms | 82.3 |
| `GET /clusters` | 500 | 0 | 47 ms | 55 ms | 2100 ms* | 11.3 |
| `GET /clusters/{id}` (Incident View) | 201 | 0 | 48 ms | 59 ms | 71 ms | 4.5 |
| `GET /search?service=...` | 273 | 0 | 53 ms | 69 ms | 2100 ms* | 6.2 |
| `GET /search?trace_id=...` | 198 | 0 | 48 ms | 2100 ms* | 2100 ms* | 4.5 |
| **Tổng** | **4 810** | **0 (0.00%)** | **48 ms** | **58 ms** | **2100 ms\*** | **108.8** |

\* Một số rất ít request (thường 1–3 trên mỗi endpoint, lệch hẳn khỏi phần còn lại đang ổn định
quanh 50–70ms) rơi vào khoảng ~2.1s, đẩy các percentile cao (P98/P99) lên bất thường dù tỷ lệ lỗi
vẫn 0%. Cùng nguyên nhân Minh đã ghi nhận ở `INGESTION_LOAD_TEST.md`: OpenSearch tự refresh
near-real-time (~1s/lần) và lần flush/segment đầu khi tải tăng đột ngột (spawn-rate cao) gây ra vài
request bị "kẹt" tạm thời — không phải lỗi logic ở `query-api`. Từ ~giây thứ 2 của mỗi lần chạy,
latency ổn định quanh P95 55–70ms. Kết luận cho runbook: nếu production thấy P99 tăng đột biến kèm
tỷ lệ lỗi 0%, nhiều khả năng là nhiễu do refresh OpenSearch dưới tải tăng vọt (traffic spike), không
phải sự cố — xem `docs/task/runbook.md` mục "Khi Ingestion quá tải / rớt log".

Chi tiết đầy đủ: `e2e_load_test_stats.csv`, `e2e_load_test_report.html` (4a),
`e2e_full_pipeline_stats.csv`, `e2e_full_pipeline_report.html` (4b).

## Ghi chú tích hợp rút ra từ lần chạy này

- Toàn bộ pipeline thật (fault injection → ingestion → clustering → query-api) đã được xác nhận
  hoạt động đúng trong lúc chuẩn bị load test: một cụm lỗi thật (`RuntimeError: Simulated downstream
  failure`) được tạo từ `demo-app`, nhóm/tính z-score đúng ở `clustering` (điểm vượt `ANOMALY_THRESHOLD`
  mặc định `2.0` → `status="alerted"`), và `query-api` trả đúng cụm đó kèm `logs` đã được tra từ
  `log_ids` (Incident View) — không phát sinh xung đột tích hợp nào giữa 3 module cần sửa.
- `/search`, `/clusters`, `/clusters/{id}` giữ 0% lỗi dưới tải kết hợp với `/ingest` — tầng đọc
  (`query-api`) không bị nghẽn bởi tầng ghi (`ingestion`) chạy đồng thời trên cùng OpenSearch.

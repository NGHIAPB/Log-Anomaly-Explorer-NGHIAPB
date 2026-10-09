# ingestion — Minh

Nhận structured log từ demo-app, validate schema, ghi vào kho dữ liệu. Nền tảng để Clustering (Nam) và Search/Incident View (Nghĩa) đọc dữ liệu.

## Trách nhiệm

- [x] Chọn **một** trong Elasticsearch/OpenSearch hoặc ClickHouse, cài đặt `LogStore` thật trong `src/storage.py` (đang là `InMemoryLogStore` tạm thời) — đã chọn **OpenSearch**, cài `OpenSearchLogStore`; `InMemoryLogStore` vẫn giữ lại làm backend dev/test nhẹ (`LOG_STORE_BACKEND=memory`)
- [x] Thiết kế index/table cho `StructuredLog` (theo [`log-schema.json`](../docs/architect/contracts/log-schema.json)) — xem `LOG_INDEX_MAPPING` trong `src/storage.py`
- [x] Hoàn thiện quarantine: nơi lưu log sai schema (hiện chỉ lưu trong bộ nhớ, `write_quarantine`) — ghi vào index `logs-quarantine` riêng (OpenSearch) hoặc danh sách in-memory (backend `memory`)
- [x] Lên lịch chạy `src/retention.py` định kỳ (cron/scheduler) — số ngày lưu lấy từ biến môi trường `RETENTION_DAYS`, **không hardcode**. Có 2 lựa chọn (xem phần "Retention" bên dưới): scheduler trong tiến trình FastAPI, hoặc script `scripts/run_retention.py` cho OS cron/k8s CronJob
- [x] Viết load test tầng ingestion trong `../load-tests/` — xem [`../load-tests/INGESTION_LOAD_TEST.md`](../load-tests/INGESTION_LOAD_TEST.md)

## Hợp đồng đang tuân theo

- Input: `POST /ingest` nhận log theo [`log-schema.json`](../docs/architect/contracts/log-schema.json). Sai schema → `400` + quarantine (không vào index chính), đúng [`api-contract.md`](../docs/architect/contracts/api-contract.md)
- Output: phục vụ `search()` cho Nghĩa, `get_by_ids()` phục vụ tra log theo `log_ids` của một `ClusterRecord` (dùng cho Incident View của Nghĩa và để Nam đọc lại log gốc)
- Chi tiết request/response: [`api-contract.md`](../docs/architect/contracts/api-contract.md)

**Quan trọng cho Nam & Nghĩa**: đừng tự khởi tạo `LogStore` riêng — import
`get_store()` từ `ingestion.src.storage` để dùng chung một kết nối/cấu hình với
Ingestion:

```python
from ingestion.src.storage import get_store

store = get_store()
logs = store.search(service="demo-web")      # GET /search
logs = store.get_by_ids(cluster_record["log_ids"])  # GET /clusters/{id}
```

## Chạy thử

```bash
# 1. OpenSearch cuc bo (dev) - xem docker-compose.yml
docker compose -f docker-compose.yml up -d

# 2. Ingestion service
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

Không có Docker? Dùng backend nhẹ không persist (không dùng cho evidence/demo thật):

```bash
LOG_STORE_BACKEND=memory uvicorn src.main:app --reload --port 8000
```

```bash
curl -X POST http://localhost:8000/ingest -H "Content-Type: application/json" -d '{
  "timestamp": "2026-10-01T09:00:00Z", "level": "ERROR", "service": "demo-web",
  "trace_id": "abc123", "span_id": "span1", "message": "Simulated failure"
}'
```

### Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `LOG_STORE_BACKEND` | `opensearch` | `opensearch` (thật) hoặc `memory` (dev/test nhẹ) |
| `OPENSEARCH_URL` | `http://localhost:9200` | Endpoint OpenSearch |
| `OPENSEARCH_INDEX` | `logs` | Index log hợp lệ |
| `OPENSEARCH_QUARANTINE_INDEX` | `logs-quarantine` | Index log sai schema |
| `OPENSEARCH_USERNAME` / `OPENSEARCH_PASSWORD` | — | Tùy chọn, nếu bật security plugin |
| `RETENTION_DAYS` | `30` | Số ngày giữ log trước khi retention job xóa |
| `RETENTION_INTERVAL_HOURS` | `24` | Chu kỳ chạy retention job trong tiến trình (đặt `0` để tắt, dùng cron ngoài thay thế) |
| `RETENTION_RUN_ON_STARTUP` | `false` | `true` để chạy retention 1 lần ngay khi service khởi động (hữu ích khi demo/test) |

### Retention

Hai cách chạy `run_retention()` định kỳ, chọn một tùy cách triển khai:

1. **Scheduler trong tiến trình** (mặc định, đã bật sẵn trong `src/main.py` qua
   `APScheduler`) — không cần thêm hạ tầng, chạy mỗi `RETENTION_INTERVAL_HOURS` giờ.
2. **OS cron / k8s CronJob** — đặt `RETENTION_INTERVAL_HOURS=0` để tắt scheduler
   trong tiến trình, rồi lên lịch chạy riêng:
   ```bash
   # crontab vi du: 03:00 moi ngay
   0 3 * * * cd /path/to/repo && RETENTION_DAYS=30 python -m ingestion.scripts.run_retention
   ```

## Evidence sở hữu

**Load test tầng ingestion** — đo throughput (log/giây) và tỷ lệ lỗi khi tải tăng.
Script dùng chung tại `../load-tests/locustfile.py` (class `IngestionUser`), kết quả
và cách chạy lại tại [`../load-tests/INGESTION_LOAD_TEST.md`](../load-tests/INGESTION_LOAD_TEST.md).

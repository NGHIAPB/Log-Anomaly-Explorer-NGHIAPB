# API Contract

Hợp đồng giữa tầng dữ liệu (ingestion, clustering) và query-api (Nghĩa). Đóng băng ở Ngày 0 — mọi thay đổi phải thông báo cho cả nhóm trước khi sửa.

## Ingestion Service (Minh)

### `POST /ingest`
Nhận một structured log, validate theo [`log-schema.json`](./log-schema.json).

- **Request body**: theo `log-schema.json`
- **Response 202**: `{ "accepted": true, "log_id": "<id>" }`
- **Response 400**: log sai schema → đưa vào quarantine, không chèn vào index chính
  ```json
  { "accepted": false, "reason": "schema_validation_failed", "details": "..." }
  ```

## Query & Incident API (Nghĩa)

### `GET /search`
Tìm log thô theo field — **không phải** semantic/vector search.

| Query param | Kiểu | Bắt buộc |
|---|---|---|
| `from`, `to` | ISO 8601 datetime | Không (mặc định 24h gần nhất) |
| `service` | string | Không |
| `trace_id` | string | Không |
| `q` | string (full-text trên `message`) | Không |

Response: `{ "total": 0, "results": [ /* StructuredLog[] theo log-schema.json */ ] }`

### `GET /clusters`
Danh sách cụm bất thường, đọc từ dữ liệu do Nam ghi theo [`cluster-record.schema.json`](./cluster-record.schema.json).

| Query param | Kiểu | Ghi chú |
|---|---|---|
| `status` | `anomalous` \| `alerted` \| `normal` | Lọc theo trạng thái |
| `since` | ISO 8601 datetime | Mặc định `now - RETENTION_DAYS` (retention hiện hành của ingestion, xem `ingestion/README.md`) |

Response: `{ "total": 0, "clusters": [ /* ClusterRecord[] theo cluster-record.schema.json */ ] }`

### `GET /clusters/{cluster_id}`
Chi tiết một cụm — dùng cho Incident View. Trả về toàn bộ `ClusterRecord`
([`cluster-record.schema.json`](./cluster-record.schema.json): `cluster_id`, `signature`,
`score`, `log_ids`, `trace_ids`, `first_seen`, `last_seen`, `status`) cộng thêm `logs` đã
tra từ `log_ids` — giữ nguyên các field gốc thay vì cắt bớt, vì `first_seen`/`last_seen`/
`signature` đều cần cho runbook (xem `docs/task/runbook.md`).

Response:
```json
{
  "cluster_id": "...",
  "signature": "...",
  "score": 0.0,
  "log_ids": ["..."],
  "trace_ids": ["..."],
  "first_seen": "...",
  "last_seen": "...",
  "status": "anomalous",
  "logs": [ /* StructuredLog[] theo log-schema.json, tra ve tu log_ids */ ]
}
```

## Alert (Nam → kênh thông báo ngoài)

Khi `score > ngưỡng`, Clustering service tự gọi webhook/email cấu hình sẵn — **không** đi qua query-api. Payload tối thiểu:

```json
{ "cluster_id": "...", "score": 0.0, "service": "...", "first_seen": "..." }
```

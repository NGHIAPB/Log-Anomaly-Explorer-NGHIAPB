# query-api — Nghĩa (nhóm trưởng)

Search log + Incident View (chi tiết cụm + liên kết trace/request). Cũng là nơi tổng hợp tích hợp chung của cả nhóm.

## Trách nhiệm

- [x] Nối `GET /search` sang `LogStore` thật của Minh (`ingestion.src.storage.get_store()`)
- [x] Nối `GET /clusters`, `GET /clusters/{id}` sang dữ liệu `ClusterRecord` thật của Nam (`clustering.src.storage.get_cluster_store()`)
- [x] Điền đầy đủ `logs` trong response `/clusters/{id}` bằng cách tra `log_ids` → `LogStore` — đây chính là Incident View
- [x] Giữ đồng bộ 3 hợp đồng trong `docs/architect/contracts/` khi có thay đổi, thông báo cả nhóm — đã kiểm tra lại, code thật của Minh/Nam/Nghĩa đang khớp 100% với cả 3 hợp đồng, không cần sửa
- [x] Review tích hợp giữa code của Mạnh/Minh/Nam — đã chạy thật toàn bộ pipeline (demo-app → ingestion → clustering → query-api) với OpenSearch thật, không phát hiện xung đột cần sửa
- [x] Hoàn thiện `docs/task/runbook.md` và chạy load test end-to-end trong `../load-tests/`
- [x] Đóng gói deploy lên Web: `Dockerfile` cho 4 service + `docker-compose.yml` + reverse-proxy (Caddy) ở gốc repo — xem [`docs/task/deployment.md`](../docs/task/deployment.md)
- [x] Xây giao diện người dùng riêng cho Search + Incident View (không phải Swagger UI), deploy Vercel — xem [`../web/`](../web/)

## Hợp đồng đang tuân theo

[`api-contract.md`](../docs/architect/contracts/api-contract.md) — phần "Query & Incident API".

## Chạy thử

`query-api` import trực tiếp `ingestion.src.storage` và `clustering.src.storage` (dùng chung
`LogStore`/`ClusterStore`, xem `src/main.py`), nên **phải chạy từ thư mục gốc repo** (giống cách
Nam chạy `clustering`), không phải từ trong `query-api/`:

```bash
# Từ thư mục gốc repo:
pip install -r query-api/requirements.txt
docker compose -f ingestion/docker-compose.yml up -d   # OpenSearch cục bộ (dùng chung với ingestion/clustering)
uvicorn query-api.src.main:app --reload --port 8002
```

Không có Docker? Dùng backend nhẹ không persist — **phải khớp với backend mà ingestion/clustering
đang dùng**, nếu không sẽ đọc một kho dữ liệu trống khác với nơi 2 service đó ghi vào:

```bash
LOG_STORE_BACKEND=memory CLUSTER_STORE_BACKEND=memory uvicorn query-api.src.main:app --reload --port 8002
```

## Evidence sở hữu

- **Runbook**: [`../docs/task/runbook.md`](../docs/task/runbook.md)
- **Load test end-to-end**: [`../load-tests/END_TO_END_LOAD_TEST.md`](../load-tests/END_TO_END_LOAD_TEST.md) — mô phỏng tải thật qua toàn bộ pipeline (ingest → cluster → alert → query), số liệu đo thật (0% lỗi, ~109 req/s tổng hợp, P95 ~58ms)
- **Deploy (Web)**: [`../docs/task/deployment.md`](../docs/task/deployment.md) — `docker compose up -d --build` ở gốc repo dựng toàn bộ stack (OpenSearch + 4 service + gateway), đã test thật: fault injection → clustering (worker tự chạy theo chu kỳ) → alert → Incident View, toàn bộ qua một cổng `:80` duy nhất
- **Giao diện người dùng**: [`../web/`](../web/) (React + Vite + Tailwind/shadcn, deploy Vercel) — đã test thật qua trình duyệt (Playwright + Chrome): danh sách cụm bất thường → Incident View → bấm trace → search tự lọc, toàn bộ luồng dữ liệu thật từ backend

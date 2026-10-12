# Deployment — Log Anomaly Explorer

> Sở hữu: Nghĩa (nhóm trưởng). Đáp ứng yêu cầu "Môi trường deploy: Web" của đề bài —
> đóng gói toàn bộ backend + database thành một stack Docker chạy được trên bất kỳ
> máy chủ Linux nào có Docker, công khai qua một cổng web duy nhất.

## Kiến trúc deploy

```
Internet ──▶ gateway (Caddy, :80/:443)
                 │
                 ├── /ingest        ──▶ ingestion   (:8000, Minh)
                 ├── /search        ──▶ query-api   (:8002, Nghĩa)
                 ├── /clusters*     ──▶ query-api   (:8002, Nghĩa)
                 ├── /docs,/redoc,/openapi.json ──▶ query-api (Swagger UI)
                 ├── /demo/*        ──▶ demo-app    (:8001, Mạnh)
                 └── /health        ──▶ query-api

clustering (Nam) — job nền, không có HTTP endpoint, tự đọc/ghi OpenSearch theo chu kỳ.

synthetic-traffic (Nghĩa) — job nền, tự gọi vào demo-app mỗi 5 phút (mặc định) để
dashboard luôn có dữ liệu sống mà không cần ai bắn tay. Xem mục riêng bên dưới.

Tất cả 4 service + clustering đều đọc/ghi chung 1 OpenSearch (database), nằm
HOÀN TOÀN NỘI BỘ trong mạng Docker — không publish port 9200 ra ngoài, không
bao giờ bị truy cập trực tiếp từ Internet.
```

File liên quan (tất cả ở gốc repo, đều là phần việc deploy của Nghĩa):

| File | Vai trò |
|---|---|
| `docker-compose.yml` | Định nghĩa toàn bộ stack (opensearch, ingestion, demo-app, clustering, query-api, synthetic-traffic, gateway) |
| `ingestion/Dockerfile`, `demo-app/Dockerfile`, `clustering/Dockerfile`, `query-api/Dockerfile` | Image cho từng service — build từ **gốc repo** (không phải từ trong từng thư mục), vì `ingestion`/`clustering`/`query-api` import chéo lẫn nhau và đọc schema trong `docs/architect/contracts/` theo đường dẫn tương đối tới gốc repo |
| `deploy/Caddyfile` | Cấu hình reverse-proxy — cổng vào duy nhất, định tuyến theo path |
| `deploy/synthetic_traffic.py`, `deploy/Dockerfile.synthetic-traffic` | Traffic generator nền — xem mục riêng bên dưới |
| `.env.example` | Mẫu biến môi trường cho `docker-compose.yml` |
| `.dockerignore` | Loại trừ `.venv/`, `.git/`, cache... khỏi build context |

## Synthetic traffic — dữ liệu "sống" tự động, không cần bắn tay

`demo-app` hoàn toàn thụ động — **không** có cơ chế tự sinh log nào (chỉ phản ứng khi có
request HTTP gọi tới `/api/items`/`/simulate-error`). Container `synthetic-traffic` giải
quyết việc này: mỗi `SYNTHETIC_TICK_SECONDS` giây (mặc định **300s = 5 phút**), tự gọi vào
demo-app, chọn ngẫu nhiên 1 trong 5 kiểu theo trọng số để log luôn đa dạng:

| Kiểu | Tỷ lệ | Hiệu ứng |
|---|---|---|
| `normal` | 60% | 1 log INFO (baseline), ~30% kèm header mobile |
| `timeout` | 10% | 1 log WARN (request giả lập chậm) |
| `quarantine` | 10% | 1 log sai schema — test đường quarantine của Ingestion |
| `anomaly` | 12% | Burst ngắn (5-12s) log ERROR, cường độ ngẫu nhiên — có thể lên `anomalous` |
| `alert` | 8% | Burst mạnh hơn (10-20s) — nhiều khả năng vượt `ANOMALY_THRESHOLD` → `alerted` |

**Vì sao cường độ ngẫu nhiên hoá mỗi lần** (không dùng số cố định): baseline của Nam tự
thích nghi theo thời gian (xem `docs/task/runbook.md`) — lặp đúng một khuôn mẫu burst nhiều
lần sẽ khiến z-score giảm dần tới khi hệ thống ngừng coi đó là bất thường. Ngẫu nhiên hoá
giúp vẫn có alert thật đều đặn qua nhiều ngày thay vì "trơ" dần.

**Tắt tạm thời** (vd. lúc đang demo trực tiếp, tránh traffic giả xen vào thao tác tay):
```bash
docker compose stop synthetic-traffic
docker compose start synthetic-traffic   # bật lại
```

### Bắn thủ công (không đợi chu kỳ 5 phút)

Chạy song song với container nền đang chạy bình thường, không xung đột (dùng `docker exec`
để spawn một tiến trình Python riêng bên trong cùng container):

```bash
# 1 tick ngau nhien ngay lap tuc
docker exec log-anomaly-synthetic-traffic python synthetic_traffic.py --once

# 10 tick lien tiep, cach nhau 2s - nhanh chong co du lieu da dang truoc khi demo
docker exec log-anomaly-synthetic-traffic python synthetic_traffic.py --count 10 --interval 2

# Ep dung 1 kieu cu the (bo qua random) - vd. muon chac chan co ngay 1 cum "alerted"
docker exec log-anomaly-synthetic-traffic python synthetic_traffic.py --once --kind alert
```

`--kind` nhận 1 trong 5 giá trị: `normal`, `timeout`, `quarantine`, `anomaly`, `alert`.

**Lưu ý quan trọng**: `ingestion/docker-compose.yml` (của Minh) là file riêng, chỉ
dựng OpenSearch cho **dev cục bộ khi chạy `uvicorn --reload` từng service thủ công**
(xem `ingestion/README.md`). File `docker-compose.yml` ở gốc repo là một stack
**khác, độc lập, đầy đủ** — dùng cho deploy thật/demo evidence. Hai file không
dùng chung volume/network, chạy được song song không xung đột (tên container
và volume khác nhau).

## Deploy local để kiểm thử (đã test thật)

```bash
docker compose up -d --build
```

Sau khi tất cả container `healthy`:

```bash
curl http://localhost/health                         # {"status":"ok","service":"query-api"}
curl http://localhost/search                          # log 24h gần nhất
curl http://localhost/clusters                         # cụm bất thường
curl -X POST http://localhost/ingest -H "Content-Type: application/json" -d '{...}'
curl "http://localhost/demo/simulate-error?rate=1.0"    # fault injection qua gateway
```

**Giao diện người dùng thật** (Search + Incident View, không phải Swagger UI): [`web/`](../../web/)
— React + Vite, deploy lên Vercel, xem [`web/README.md`](../../web/README.md). Khi dev local
cùng stack này, trỏ `VITE_API_BASE_URL` về `http://localhost` (gateway); khi trỏ sang một
backend đã deploy thật cho một trang Vercel (chạy HTTPS), backend đó cũng phải là HTTPS —
trình duyệt chặn Mixed Content nếu gọi HTTP thuần từ trang HTTPS.

**Swagger UI tự sinh của FastAPI** (bổ sung, dùng để gọi thử API thô trực tiếp từ trình duyệt,
nút "Try it out"):

- **http://localhost/docs** — Swagger UI của `query-api` (Search + Incident View), proxy qua
  gateway port `:80`.
- http://localhost:8000/docs — `ingestion` (`POST /ingest`)
- http://localhost:8001/docs — `demo-app` (`/api/items`, `/simulate-error`)

(`ingestion`/`demo-app` xem trực tiếp qua port riêng, không gộp vào gateway `/docs` vì Swagger UI
của mỗi service tự tham chiếu `/openapi.json` tuyệt đối — gộp chung sẽ load nhầm schema.)

Đã chạy thật kịch bản này (xem lịch sử phát triển): build 4 image, `docker compose up -d`,
bắn một đợt fault injection qua `http://localhost/demo/simulate-error`, và **không cần can
thiệp thủ công** — container `clustering` (job nền, chu kỳ mặc định 60s) tự nhặt log lỗi mới,
tính anomaly score, chuyển `status="alerted"`, và `GET http://localhost/clusters/{id}` trả về
đúng Incident View — toàn bộ qua **một cổng 80 duy nhất**, đúng mô hình "deploy lên Web".

Cũng có thể gọi trực tiếp từng service qua port riêng khi cần debug (không qua gateway):
`:8000` (ingestion), `:8001` (demo-app), `:8002` (query-api) — các port này vẫn được publish
ra host để tiện kiểm thử, song song với gateway.

## Deploy lên một máy chủ thật (VPS / cloud VM)

1. Chuẩn bị một máy Linux (VPS, cloud VM, ...) đã cài **Docker Engine + Docker Compose
   plugin**, mở port `80` (và `443` nếu dùng domain thật).
2. Clone repo lên máy chủ đó, `cd` vào gốc repo.
3. (Tuỳ chọn) `cp .env.example .env` rồi chỉnh các biến cần thiết — xem bảng bên dưới.
   Không bắt buộc phải có `.env`, mọi biến đều có giá trị mặc định hợp lý.
4. `docker compose up -d --build`
5. Kiểm tra: `curl http://<IP-may-chu>/health`

### Gắn domain thật + HTTPS tự động (tuỳ chọn)

Trỏ bản ghi DNS A của domain về IP máy chủ, rồi trong `.env`:

```bash
PUBLIC_ADDRESS=log-anomaly.example.com
```

`docker compose up -d` lại — Caddy (gateway) tự động xin và gia hạn chứng chỉ HTTPS qua
Let's Encrypt, không cần cấu hình gì thêm. Không có domain? Để mặc định `PUBLIC_ADDRESS=:80`
— stack vẫn chạy HTTP thuần qua địa chỉ IP, đủ dùng để demo/chấm điểm.

### Biến môi trường (`.env`, xem thêm `.env.example`)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `PUBLIC_ADDRESS` | `:80` | Địa chỉ gateway lắng nghe — đặt domain thật để bật HTTPS tự động |
| `RETENTION_DAYS` | `30` | Số ngày giữ log (ingestion) — cũng là mặc định `since` của `GET /clusters` |
| `RETENTION_INTERVAL_HOURS` | `24` | Chu kỳ chạy retention job trong ingestion |
| `CLUSTERING_WINDOW_MINUTES` | `10` | Độ dài khung thời gian clustering xét mỗi lần chạy |
| `CLUSTERING_BASELINE_WINDOWS` | `6` | Số khung lịch sử dùng tính baseline |
| `CLUSTERING_INTERVAL_SECONDS` | `60` | Chu kỳ chạy của job clustering |
| `ANOMALY_THRESHOLD` | `2.0` | Ngưỡng z-score để chuyển `status="alerted"` |
| `ALERT_WEBHOOK_URL` | *(rỗng)* | Webhook nhận alert thật (vd. Slack incoming webhook) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | *(rỗng)* | Endpoint OTLP/HTTP nếu có OTel Collector riêng; rỗng = demo-app in trace ra `docker logs` |

## Những gì CHƯA nằm trong MVP deploy này (có chủ đích)

- **Không có xác thực/API key** trên `query-api`/`ingestion` — ngoài phạm vi MVP đề bài
  (chỉ yêu cầu search/ingestion/clustering/alert/incident view hoạt động đúng).
- **OpenSearch chạy single-node, không bật security plugin** — giống hệt lựa chọn đã chốt
  ở `ingestion/docker-compose.yml` (dev-grade), chấp nhận được cho MVP vì không publish
  port 9200 ra ngoài; nâng cấp lên cluster nhiều node có bảo mật là việc của một giai đoạn sau.
- **Chưa có CI/CD** (build/push image tự động khi push code) — nằm ngoài yêu cầu GitHub
  evidence bắt buộc của đề bài (fault injection, labeled incidents, precision/recall,
  load test, runbook — không có mục "CI/CD").

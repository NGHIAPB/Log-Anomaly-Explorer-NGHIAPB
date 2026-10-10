# web — Giao diện người dùng (Nghĩa)

Frontend cho Log Anomaly Explorer — UI riêng cho sản phẩm (không phải Swagger UI tự sinh),
bám đúng luồng "3. SEARCH & INCIDENT VIEW" trong `docs/architect/architecture-sod.png`.
Deploy lên Vercel; gọi trực tiếp `query-api` (Nghĩa) qua HTTP, không có backend riêng của
frontend (không có API route/BFF trong Next.js này).

Next.js 16 (App Router) + TypeScript + Tailwind CSS v4.

## Tính năng

- **Danh sách cụm bất thường** (`/`) — lọc theo `status` (normal/anomalous/alerted), sắp xếp
  theo anomaly score, click vào một cụm để xem chi tiết.
- **Incident View** (`/clusters/[id]`) — chi tiết cụm (score, signature, first/last seen),
  toàn bộ log liên quan, danh sách trace/request — click một trace để nhảy sang Search đã lọc
  sẵn theo đúng trace đó (liên kết trace/request theo đúng kiến trúc đã vẽ).
- **Search log** (`/`, cuối trang) — lọc theo `service`, `trace_id`, từ khoá (`q`), thời gian.

## Hợp đồng đang tuân theo

Gọi trực tiếp 3 endpoint của `query-api`: `GET /search`, `GET /clusters`, `GET /clusters/{id}`
— xem [`../docs/architect/contracts/api-contract.md`](../docs/architect/contracts/api-contract.md).
Types trong [`src/lib/api.ts`](src/lib/api.ts) khớp với
[`log-schema.json`](../docs/architect/contracts/log-schema.json) và
[`cluster-record.schema.json`](../docs/architect/contracts/cluster-record.schema.json).

## Chạy thử (dev local)

Cần `query-api` đang chạy thật (xem `docker-compose.yml` ở gốc repo hoặc
`query-api/README.md`), vì CORS trên `query-api` đã mở sẵn cho frontend gọi trực tiếp
(`allow_origins=["*"]`, chỉ cho `GET` — xem `query-api/src/main.py`).

```bash
# Từ thư mục gốc repo, dựng backend thật:
docker compose up -d --build

cd web
npm install
cp .env.example .env.local      # NEXT_PUBLIC_API_BASE_URL=http://localhost:8002 (mặc định)
npm run dev                      # http://localhost:3000
```

## Deploy lên Vercel

```bash
cd web
npx vercel login       # đăng nhập tài khoản Vercel của bạn (một lần)
npx vercel              # deploy preview
npx vercel --prod       # deploy production
```

Hoặc qua dashboard: Vercel → **Add New Project** → import repo GitHub này → **Root Directory**
đặt thành `web` (bắt buộc, vì đây là monorepo nhiều thư mục) → Vercel tự nhận Next.js, không
cần cấu hình build command/output.

**Bắt buộc**: trong Vercel → Project Settings → Environment Variables, thêm
`NEXT_PUBLIC_API_BASE_URL` trỏ tới URL **public** của `query-api` (vd. domain thật đã deploy
theo [`../docs/task/deployment.md`](../docs/task/deployment.md)). Vercel không gọi được tới
`localhost` của máy bạn — thiếu biến này, UI sẽ hiện lỗi "Không kết nối được tới API".

## Evidence sở hữu

Phần của checklist "Search, Incident view" (MVP bắt buộc, xem `README.md` gốc) — UI thật
thay cho việc chỉ test qua Swagger UI/`curl`.

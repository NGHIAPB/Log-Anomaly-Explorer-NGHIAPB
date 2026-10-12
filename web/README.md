# web — Giao diện người dùng (Nghĩa)

Frontend cho Log Anomaly Explorer — UI riêng cho sản phẩm (không phải Swagger UI tự sinh),
bám đúng luồng "3. SEARCH & INCIDENT VIEW" trong `docs/architect/architecture-sod.png`.
Deploy lên Vercel; gọi trực tiếp `query-api` (Nghĩa) qua HTTP, không có backend riêng của
frontend (không có API route/BFF).

## Công nghệ

| Nhóm | Dùng |
|---|---|
| Nền tảng | React 19 + TypeScript + Vite |
| UI | Tailwind CSS v4 + shadcn/ui (Radix) + Lucide icons |
| Data fetching | TanStack Query |
| Bảng log | TanStack Table + TanStack Virtual (windowing — cụm có thể có hàng trăm log) |
| Biểu đồ | Apache ECharts (import modular, không load toàn bộ thư viện) |
| Form | React Hook Form + Zod |
| Routing | React Router |
| Thời gian | date-fns |
| Test | Vitest + React Testing Library (unit), Playwright (E2E) |

## Tính năng

- **Dashboard** (`/`) — thống kê nhanh (tổng cụm, alerted, anomalous, score cao nhất), biểu đồ
  top 10 cụm theo anomaly score, danh sách cụm dạng card (lọc theo status).
- **Incident View** (`/clusters/:id`) — chi tiết cụm (score, signature, first/last seen), toàn bộ
  log liên quan (bảng ảo hoá, click 1 dòng mở Dialog xem stack trace/metadata), danh sách
  trace — click 1 trace nhảy sang Search đã lọc sẵn.
- **Search log** (`/search`) — lọc theo `service`, `trace_id`, từ khoá, thời gian; đồng bộ 2 chiều
  với URL (`?trace_id=...`) để có thể deep-link/chia sẻ link kết quả.

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
cp .env.example .env.local      # VITE_API_BASE_URL=http://localhost:8002 (mặc định)
npm run dev                      # http://localhost:5173
```

## Test

```bash
npm run test          # unit test (Vitest + RTL) - mock fetch, khong can backend
npm run test:e2e      # E2E (Playwright) - CAN backend that dang chay + it nhat 1 cluster co san
npm run lint           # oxlint
npm run build          # type-check (tsc) + production build
```

## Deploy lên Vercel

```bash
cd web
npx vercel login       # đăng nhập tài khoản Vercel của bạn (một lần)
npx vercel              # deploy preview
npx vercel --prod       # deploy production
```

Hoặc qua dashboard: Vercel → **Add New Project** → import repo GitHub này → **Root Directory**
đặt thành `web` (bắt buộc, vì đây là monorepo nhiều thư mục) → Vercel tự nhận diện Vite, không
cần cấu hình build command/output (mặc định `npm run build` → thư mục `dist/`).

**Bắt buộc**: trong Vercel → Project Settings → Environment Variables, thêm
`VITE_API_BASE_URL` trỏ tới URL **public, HTTPS** của `query-api` (vd. domain/sslip.io đã
deploy theo [`../docs/task/deployment.md`](../docs/task/deployment.md)). Hai lưu ý quan trọng:

- Biến này được nhúng vào bundle **lúc build**, không phải lúc chạy — đổi giá trị trên Vercel
  xong phải **Redeploy** mới có hiệu lực, chỉ sửa biến không tự áp dụng cho bản đã build.
- Backend phải là **HTTPS**, không phải HTTP thuần — Vercel phục vụ trang qua HTTPS nên trình
  duyệt sẽ chặn (Mixed Content) nếu gọi sang một API HTTP thuần. Dùng `sslip.io` nếu backend
  chỉ có IP, chưa có domain thật (xem `docs/task/deployment.md`).

## Evidence sở hữu

Phần của checklist "Search, Incident view" (MVP bắt buộc, xem `README.md` gốc) — UI thật
thay cho việc chỉ test qua Swagger UI/`curl`.

# clustering — Nam

"Bộ não" phát hiện bất thường: nhóm lỗi tương tự, tính anomaly score, phát alert khi vượt ngưỡng.

## Trách nhiệm

- [x] Hoàn thiện thuật toán nhóm lỗi trong `src/clustering.py` — chuẩn hoá message (bỏ số, uuid, hex id, chuỗi trong quote) trước khi nhóm, ưu tiên dòng cuối `stack_trace` khi có (`compute_signature`), để các lỗi cùng "hình dạng" nhưng khác giá trị cụ thể được nhóm chung
- [x] Hoàn thiện cách tính baseline tần suất + anomaly score — `src/baseline.py` tính baseline (mean/stdev) thật từ lịch sử log lỗi cùng signature theo các khung thời gian (bucket) trước đó; `src/anomaly_score.py` dùng z-score so với baseline đó
- [x] Cấu hình `ANOMALY_THRESHOLD` và `ALERT_WEBHOOK_URL` cho `src/alert.py` qua biến môi trường (xem bảng dưới); `check_and_alert()` được job nền (`src/main.py`) gọi sau mỗi lần `compute_anomaly_score()`
- [x] Phối hợp với Mạnh: dùng `/simulate-error` để tạo các giai đoạn bất thường có kiểm soát, rồi điền vào `evaluation/labeled_incidents.json`
- [x] Chạy `evaluation/precision_recall.py` để có số liệu precision/recall thật (xem mục "Chạy thử end-to-end" bên dưới)

## ⚠️ Bug thật đã sửa (2026-10-12, Nghĩa — báo Nam biết trước khi merge)

**Triệu chứng phát hiện khi chạy thật trên VPS**: `demo-web` và `demo-mobile-api` cùng gây ra
lỗi có **signature giống hệt nhau** (cùng gọi chung 1 hàm lỗi trong `demo-app`). `group_similar_errors()`
cũ chỉ nhóm theo `signature`, không theo `service` — khiến log của 2 service bị gộp chung vào
1 nhóm. `anomaly_score.compute_anomaly_score()` lấy `service` từ `logs[0]` (log đầu tiên trong
nhóm) để tính `cluster_id` — tức **service đại diện cho cả cụm phụ thuộc ngẫu nhiên vào log nào
đứng đầu danh sách ở mỗi lần chạy**, không ổn định. Hậu quả quan sát được thật: một cụm
`demo-mobile-api` được tạo đúng 1 lần rồi "đứng yên mãi" — các log lỗi mobile mới sau đó (đã xác
nhận có tồn tại thật qua `GET /search?service=demo-mobile-api`) bị gộp nhầm vào cụm `demo-web`
thay vì cập nhật đúng cụm của nó.

**Đã sửa**: `group_similar_errors()` (`src/clustering.py`) giờ nhóm theo cặp `(service, signature)`
thay vì chỉ `signature`; `historical_bucket_counts()` (`src/baseline.py`) nhận thêm tham số
`service`, lọc lịch sử theo đúng cặp đó để baseline của từng service tách biệt, không tính gộp.
`src/main.py` cập nhật theo. `compute_anomaly_score()` (`anomaly_score.py`) không cần đổi vì đã
tự lấy `service` từ `logs[0]` — giờ đáng tin cậy vì mỗi nhóm chỉ còn đúng 1 service.

**Đã kiểm chứng thật**: bắn 15 lỗi `demo-web` + 10 lỗi `demo-mobile-api` trong cùng cửa sổ thời
gian → đúng 2 `ClusterRecord` riêng biệt, score lần lượt `15.0` và `10.0` (khớp chính xác số
lượng đã gửi), cùng `cluster_id` ổn định như trước khi sửa (công thức hash không đổi, chỉ sửa
cách gom nhóm đầu vào).

## Thêm so với checklist gốc

Checklist gốc không yêu cầu rõ nơi lưu `ClusterRecord` để Nghĩa đọc — để `GET /clusters`,
`GET /clusters/{id}` của Nghĩa có dữ liệu thật để nối vào (thay vì mock tĩnh), đã bổ sung:

- `src/storage.py` — `ClusterStore` (giống mô hình `LogStore` của Minh): `OpenSearchClusterStore`
  (mặc định, ghi index `clusters` trên cùng OpenSearch của Ingestion) + `InMemoryClusterStore`
  (dev/test nhẹ, `CLUSTER_STORE_BACKEND=memory`). Tự validate theo `cluster-record.schema.json`
  trước khi ghi, và tự gộp (merge) khi cùng `cluster_id` xuất hiện lại ở khung thời gian sau
  (giữ `first_seen` sớm nhất / `last_seen` muộn nhất / hợp `log_ids`, `trace_ids`) để một incident
  đang tiếp diễn không bị tách thành nhiều cluster rời rạc.
- `src/main.py` — job nền thực sự: đọc log ERROR/FATAL mới từ `LogStore` của Minh, nhóm, tính
  baseline + score, gọi alert, ghi vào `ClusterStore`. Chạy lặp (`run_forever()`, mặc định mỗi 60s)
  hoặc 1 lần (`scripts/run_clustering.py`, dùng cho OS cron/k8s CronJob).

**Quan trọng cho Nghĩa**: đừng tự khởi tạo `ClusterStore` riêng — import `get_cluster_store()`
từ `clustering.src.storage`, giống cách Ingestion đã yêu cầu dùng `get_store()`:

```python
from clustering.src.storage import get_cluster_store

cstore = get_cluster_store()
clusters = cstore.list_clusters(status="alerted")   # GET /clusters
cluster = cstore.get_cluster(cluster_id)              # GET /clusters/{id}
```

## Hợp đồng đang tuân theo

- Input: đọc log đã lưu từ Ingestion (Minh) qua `ingestion.src.storage.get_store()` (log ERROR/FATAL)
- Output: ghi `ClusterRecord` theo [`cluster-record.schema.json`](../docs/architect/contracts/cluster-record.schema.json)
  vào `ClusterStore` (`src/storage.py`), Nghĩa đọc qua `get_cluster_store()` để phục vụ Incident View
- Alert webhook: payload tối thiểu theo [`api-contract.md`](../docs/architect/contracts/api-contract.md)
  (`cluster_id`, `score`, `service`, `first_seen`) — gửi trực tiếp, không qua query-api

## Chạy thử

```bash
# 1. OpenSearch cuc bo (dung chung voi Ingestion) - xem ingestion/docker-compose.yml
docker compose -f ../ingestion/docker-compose.yml up -d

# 2. Ingestion phai dang chay (de co log dau vao)
cd ../ingestion && uvicorn src.main:app --reload --port 8000

# 3. Chay job clustering 1 lan (tu thu muc goc repo, de import package hoat dong)
cd ..
pip install -r clustering/requirements.txt
CLUSTERING_INTERVAL_SECONDS=0 python -m clustering.src.main

# hoac chay lap vo han (moi 60s, mac dinh):
python -m clustering.src.main
```

Không có Docker/OpenSearch? Dùng backend nhẹ không persist (không dùng cho evidence/demo thật):

```bash
CLUSTER_STORE_BACKEND=memory LOG_STORE_BACKEND=memory CLUSTERING_INTERVAL_SECONDS=0 python -m clustering.src.main
```

### Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `CLUSTERING_WINDOW_MINUTES` | `10` | Độ dài khung thời gian hiện tại đang xét để nhóm lỗi + tính score |
| `CLUSTERING_BASELINE_WINDOWS` | `6` | Số khung lịch sử liền trước dùng để tính baseline (mean/stdev) |
| `CLUSTERING_INTERVAL_SECONDS` | `60` | Khoảng nghỉ giữa 2 lần chạy của `run_forever()`; `0` = chạy 1 lần rồi thoát |
| `CLUSTERING_FETCH_SIZE` | `5000` | Số log tối đa đọc một lần từ `LogStore` mỗi vòng chạy |
| `ANOMALY_THRESHOLD` | `2.0` | Ngưỡng z-score để chuyển `status` sang `alerted` |
| `ALERT_WEBHOOK_URL` | *(rỗng)* | Webhook nhận alert khi vượt ngưỡng; rỗng = không gửi (vẫn cập nhật status) |
| `CLUSTER_STORE_BACKEND` | `opensearch` | `opensearch` (thật) hoặc `memory` (dev/test nhẹ) |
| `OPENSEARCH_CLUSTER_INDEX` | `clusters` | Index lưu `ClusterRecord` (dùng chung `OPENSEARCH_URL` với Ingestion) |

## Chạy thử end-to-end (tạo số liệu precision/recall thật)

```bash
# Giả sử demo-app (8001), ingestion (8000) đã chạy như trên.
# 1. Tạo một giai đoạn bất thường có kiểm soát bằng fault injection của Mạnh:
cd ../demo-app
python scripts/trigger_fault_window.py --duration 30 --rate 0.6 --fault-type error
# In ra JSON voi "started_at"/"ended_at" - dung lam window_from/window_to

# 2. Chạy job clustering 1 lần để nhóm + tính score + alert + ghi ClusterRecord:
cd ..
CLUSTERING_INTERVAL_SECONDS=0 CLUSTERING_WINDOW_MINUTES=5 python -m clustering.src.main

# 3. Dien evaluation/labeled_incidents.json: lay window_from/window_to tu buoc 1,
#    va expected_cluster_signature tu ClusterRecord vua ghi (truy van qua get_cluster_store()
#    hoac in log/debug trong buoc 2).

# 4. Chay precision/recall tren du lieu that:
python -m clustering.evaluation.precision_recall
```

## Evidence sở hữu

- **Labeled incidents**: `evaluation/labeled_incidents.json` — mỗi sự cố thật được gán nhãn thủ công.
  Hiện có **6 sự cố thật**:
  - `burst-2026-10-12-01`/`02`: tạo trong phiên chạy sạch đầu tiên (`docker compose down -v` rồi
    `up` lại), 2 đợt fault injection cách nhau ~2 phút, cùng `fault_type=error`, service `demo-web`
    — kiểm tra hệ thống nhận diện đúng **cả hai** khung thời gian bất thường của cùng một cụm.
  - `burst-2026-10-12-03`..`06` (thêm 2026-10-12, **không wipe dữ liệu đang live trên Azure VM**):
    bổ sung coverage cho `service=demo-mobile-api` và 2 `fault_type` mới (`not_found`, `db_error`,
    xem `demo-app/src/main.py`) — 2 incident gốc chỉ phủ `demo-web` + `runtimeerror`, bỏ sót cả
    service mobile và 2 loại lỗi mới thêm sau đó. Tạo bằng
    `docker exec log-anomaly-synthetic-traffic python synthetic_traffic.py --once --kind alert`
    (`deploy/synthetic_traffic.py`), xác nhận từng cặp (service, signature) qua
    `curl http://localhost:8002/clusters/{cluster_id}` ngay sau mỗi burst.
- **Precision/recall**: `evaluation/precision_recall.py` — đo trên labeled incidents ở trên; so khớp
  theo `signature` + `service` **và** khung thời gian (`first_seen`/`last_seen` chồng lấn
  `window_from`/`window_to`), không chỉ so khớp signature/service đơn thuần.

  **Kết quả đo được (2026-10-12)**, chạy thật trong container `clustering` (dùng chung OpenSearch của
  `docker-compose.yml` ở gốc repo, không phải mock), ngay sau khi tạo 4 incident mới:

  ```
  {'precision': 1.0, 'recall': 0.333, 'true_positive': 2, 'false_positive': 0, 'false_negative': 4}
  ```

  Không có cảnh báo sai nào (precision 100%), nhưng chỉ 2/6 sự cố đã gán nhãn còn ở
  `status="alerted"` **tại đúng thời điểm chạy lệnh đo** (vài phút sau khi burst, do cần thời gian
  `git push` → merge → `git pull` trên VM → `docker cp`). Đây **không phải lỗi** — khớp đúng thiết
  kế cửa sổ trượt (`CLUSTERING_WINDOW_MINUTES=10`): điểm bất thường của một burst giảm dần khi log
  của nó trôi ra khỏi cửa sổ hiện tại nếu không có log lỗi mới tiếp theo. Từng cặp (service,
  signature) mới thêm đã được xác nhận **đạt `status="alerted"` thật** ngay sau khi tạo (xem
  description trong `labeled_incidents.json`, mỗi incident ghi rõ `cluster_id` + lệnh `curl` đã
  dùng để xác nhận) — recall thấp hơn 1.0 ở phép đo tổng hợp chỉ phản ánh độ trễ đo, không phản ánh
  khả năng phát hiện thật của hệ thống tại thời điểm xảy ra sự cố.

  **Phát hiện bổ sung (cùng phiên đo)**: sau khi bắn liên tiếp 6 burst `--kind alert` nữa trong
  ~2.5 phút để cố gắng bắt tất cả tín hiệu "nóng" cùng lúc, lần đo tiếp theo cho
  `{'precision': 0.0, 'recall': 0.0, 'true_positive': 0, 'false_positive': 0, 'false_negative': 6}`
  — **không cụm nào còn `alerted`**. Nguyên nhân: `baseline.py` tính baseline từ lịch sử
  (`CLUSTERING_BASELINE_WINDOWS=6` khung gần nhất), nên bắn lặp lại nhiều burst tương tự trong thời
  gian ngắn khiến baseline "học" luôn burst đó là bình thường — đúng hành vi đã ghi chủ đích trong
  docstring của `deploy/synthetic_traffic.py` ("nếu lặp lại ĐÚNG MỘT khuôn mẫu burst nhiều lần,
  z-score sẽ giảm dần tới khi hệ thống hết còn coi đó là bất thường"). Đây là minh chứng thật cho
  cơ chế tự thích nghi của baseline, không phải một lỗi cần sửa.

  Chạy lại (từ gốc repo, sau khi `docker compose up -d`):
  ```bash
  docker cp clustering/evaluation/labeled_incidents.json log-anomaly-clustering:/app/clustering/evaluation/labeled_incidents.json
  docker exec log-anomaly-clustering python -m clustering.evaluation.precision_recall
  ```
  Để có số liệu "nóng" đại diện nhất, chạy lệnh đo **trong vòng 1-2 phút sau burst**, và tránh bắn
  lặp lại quá nhiều burst giống nhau liên tiếp (xem phát hiện ở trên).

- **Alert gửi thật (đầu-cuối)**: `scripts/alert_webhook_receiver.py` — webhook receiver tối giản
  (chỉ stdlib) để chứng minh alert **thực sự được gửi đi**, không chỉ dừng ở việc đánh dấu
  `status="alerted"` trong database.

  **Kết quả đo được (2026-10-12)** — payload thật nhận được tại webhook, đúng hợp đồng trong
  [`api-contract.md`](../docs/architect/contracts/api-contract.md) mục "Alert":

  ```json
  {
    "received_at": "2026-10-12T04:34:28.043629+00:00",
    "payload": {
      "cluster_id": "f0dc83a26d34b25458441518d7b93357",
      "score": 133.0,
      "service": "demo-web",
      "first_seen": "2026-10-12T04:31:37.198447+00:00"
    }
  }
  ```

  Cách tái lập (từ gốc repo):
  ```bash
  # 1. Chay receiver tren may host
  python -m clustering.scripts.alert_webhook_receiver --port 9099

  # 2. Tro ALERT_WEBHOOK_URL vao receiver roi dung stack (terminal khac)
  echo "ALERT_WEBHOOK_URL=http://host.docker.internal:9099/alert" > .env
  docker compose down -v && docker compose up -d    # -v de baseline sach, xem luu y ben duoi

  # 3. Ban mot dot loi that -> doi toi 60s (chu ky clustering)
  python demo-app/scripts/trigger_fault_window.py --duration 12 --rate 0.9 --interval 0.05
  ```

  **2 lưu ý quan trọng rút ra khi kiểm chứng:**
  1. **Baseline phải sạch thì burst mới "bất thường"**: nếu chạy nhiều đợt lỗi giống hệt nhau liên
     tiếp trên cùng dữ liệu, z-score của đợt sau **giảm dần** (đo thực tế: đợt lỗi 138 log chỉ đạt
     score `0.639` → không alert) vì baseline đã "học" rằng mức đó là bình thường với signature này.
     Đây là hành vi **đúng** của thuật toán, không phải lỗi — nhưng khi demo/kiểm thử alert cần
     `docker compose down -v` trước để mô phỏng đúng tình huống "sự cố xảy ra lần đầu".
  2. **Alert hiện lặp lại mỗi chu kỳ** (đo thực tế: 2 alert trong ~70s với `CLUSTERING_INTERVAL_SECONDS=60`)
     khi score còn vượt ngưỡng — chưa có cơ chế chống trùng/cooldown. Một sự cố kéo dài 30 phút sẽ
     sinh ~30 alert giống nhau. Xem `docs/task/runbook.md` mục "Khi nhận được Alert".

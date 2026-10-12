# Runbook — Log Anomaly Explorer

> Sở hữu: Nghĩa (nhóm trưởng). Điền dần khi hệ thống đã chạy thật; đây là khung bắt buộc cho GitHub evidence "runbook".

## Khi nhận được Alert

1. **Nhận alert** (webhook/email, payload từ `ALERT_WEBHOOK_URL` — cấu hình trong `clustering/src/alert.py`)
   — nội dung gồm `cluster_id`, `score`, `service`, `first_seen`.

   > ⚠️ **Alert hiện lặp lại mỗi chu kỳ clustering** (mặc định 60s, `CLUSTERING_INTERVAL_SECONDS`)
   > trong suốt thời gian score còn vượt ngưỡng — chưa có cơ chế chống trùng/cooldown. Một sự cố
   > kéo dài 30 phút sẽ sinh ~30 alert **giống hệt nhau cho cùng một `cluster_id`**. Khi xử lý:
   > coi nhiều alert cùng `cluster_id` là **một sự cố duy nhất**, đừng mở nhiều incident song song.
   > Nếu kênh nhận alert (Slack/email) bị nhiễu quá mức, tạm thời tăng `CLUSTERING_INTERVAL_SECONDS`
   > hoặc `ANOMALY_THRESHOLD` cho tới khi có cơ chế dedup.
   >
   > **Lưu ý về baseline**: nếu cùng một loại lỗi lặp lại đều đặn nhiều khung thời gian liên tiếp,
   > z-score sẽ **giảm dần** và hệ thống sẽ **ngừng alert** dù lỗi vẫn đang xảy ra (baseline đã coi
   > mức lỗi đó là "bình thường"). Đây là hành vi đúng của thuật toán phát hiện bất thường dựa trên
   > baseline, nhưng nghĩa là: **alert im lặng không đồng nghĩa với hết lỗi** — với sự cố kéo dài,
   > hãy theo dõi thêm `GET /search?service=...` hoặc số log ERROR tuyệt đối, đừng chỉ dựa vào alert.
2. **Mở Incident View**: `GET /clusters/{cluster_id}` (query-api, port `8002`) để xem chi tiết cụm —
   `score`, `status`, `signature`, `first_seen`/`last_seen`, và `logs` (đã tra sẵn từ `log_ids`, không
   cần tự gọi `/search` để lấy từng log một).
3. **Lần theo trace/request**: lấy một `trace_id` cụ thể trong `trace_ids` của response trên, rồi gọi
   `GET /search?trace_id=<id>` để xem toàn bộ log (kể cả log không phải ERROR/FATAL, vd. request bắt
   đầu bằng `INFO`) của đúng request đã gây lỗi — tái hiện lại trình tự xử lý request đó.
4. **Xác định phạm vi ảnh hưởng**:
   - Service nào: field `service` trong payload alert (không có trong response `/clusters/{id}` theo
     `api-contract.md` — field này chỉ nội bộ của clustering, dùng cho alert/đo precision-recall; nếu
     cần xem lại, suy ra từ `service` của các log trong `logs`).
   - Từ khi nào đến khi nào: `first_seen` → `last_seen` của cụm.
   - Quy mô: `len(logs)` log liên quan, `len(trace_ids)` request riêng biệt bị ảnh hưởng.
   - Mức độ bất thường: `score` so với `ANOMALY_THRESHOLD` (mặc định `2.0`, xem `clustering/README.md`)
     — score càng cao so với ngưỡng, tần suất lỗi lệch khỏi baseline lịch sử càng mạnh.
5. **Hành động theo nhóm lỗi** (dựa trên `signature` — message đã chuẩn hoá hoặc dòng cuối stack trace,
   xem `clustering/src/clustering.py`):
   - **Lỗi hạ tầng/downstream** (timeout, connection refused, 5xx từ service phụ thuộc): kiểm tra health
     của service đó trước; nếu service phụ thuộc là bên ngoài (đối tác tích hợp), liên hệ đối tác kèm
     `trace_id` cụ thể làm bằng chứng tái hiện lỗi.
   - **Lỗi do một bản deploy gần đây** (signature mới xuất hiện đúng lúc `first_seen`, trùng thời điểm
     deploy): rollback bản deploy đó trước, xác nhận `score` giảm ở lần chạy `clustering` kế tiếp
     (chu kỳ `CLUSTERING_INTERVAL_SECONDS`, mặc định 60s) rồi mới tìm root cause kỹ hơn.
   - **Lỗi dữ liệu/logic ứng dụng** (vd. "User not found", validation lỗi): không rollback hạ tầng —
     xử lý ở tầng code/dữ liệu, dùng `logs` trong Incident View (có `stack_trace`/`metadata`) để debug.
   - **Service crash/treo** (log dừng hẳn, không còn log mới dù lỗi đang xảy ra): restart service, vì
     lúc đó pipeline không nhận được log mới để `clustering` cập nhật cụm.
6. **Đóng sự cố**: cập nhật trạng thái cụm (hiện `write_cluster` tự gộp theo `cluster_id` ở lần chạy
   sau — chưa có API cho người vận hành tự đổi `status` thủ công; nếu cần, coi `status="alerted"` là
   đã được xử lý xong khi tần suất lỗi mới giảm về dưới `ANOMALY_THRESHOLD` ở lần `clustering` kế tiếp).
   Ghi chú root cause (loại lỗi ở bước 5, thời gian xử lý, hành động đã làm) kèm `cluster_id`,
   `window_from`/`window_to` thực tế của sự cố, để Nam điền vào
   `clustering/evaluation/labeled_incidents.json` làm ground-truth đo precision/recall.

## Khi hệ thống báo động giả (false positive) nhiều

Alert dựa trên z-score so với baseline tần suất lịch sử (xem `clustering/src/baseline.py` +
`anomaly_score.py`), nên false positive thường do baseline chưa đủ dữ liệu lịch sử hoặc ngưỡng quá
nhạy so với mức dao động tự nhiên của một service cụ thể, chứ không phải lỗi logic tính toán.

1. Xác nhận false positive thật (không phải lỗi thật bị bỏ sót nguyên nhân): so `logs` trong Incident
   View với hành vi thực tế của service tại thời điểm `first_seen`–`last_seen`.
2. Kiểm tra `CLUSTERING_BASELINE_WINDOWS` (mặc định `6` khung) có đủ lớn không — baseline tính trên
   quá ít khung lịch sử (vd. service mới triển khai, chưa có 6 khung dữ liệu "bình thường") sẽ có
   mean/stdev không ổn định, dễ bắn alert sai.
3. Nếu baseline đã đủ ổn định nhưng ngưỡng vẫn quá nhạy: tăng `ANOMALY_THRESHOLD` (env var của
   `clustering`, mặc định `2.0`) theo bước nhỏ (vd. `2.0` → `2.5`), chạy lại `precision_recall.py`
   trên `labeled_incidents.json` hiện có để xác nhận recall không giảm quá nhiều trước khi áp dụng.
4. Phối hợp với Nam: mọi thay đổi `ANOMALY_THRESHOLD`/`CLUSTERING_WINDOW_MINUTES`/
   `CLUSTERING_BASELINE_WINDOWS` ảnh hưởng trực tiếp tới số liệu precision/recall đã ghi nhận —
   báo trước khi đổi để Nam đo lại và cập nhật evidence.

## Khi Ingestion quá tải / rớt log

1. **Phân biệt "quá tải" (log vẫn vào nhưng chậm) với "rớt log" (log mất hẳn)**:
   - `POST /ingest` trả `202` nhưng tăng latency → quá tải, log không mất.
   - `POST /ingest` timeout/connection refused ở tầng demo-app (`emit_log()` trong
     `demo-app/src/main.py` nuốt lỗi gửi log có chủ đích, không crash app demo) → log bị rớt thật,
     không vào cả index chính lẫn quarantine.
   - Log vào `400` + index `logs-quarantine` → **không phải lỗi hạ tầng**, đây là hành vi đúng theo
     `api-contract.md` cho log sai schema — không cần xử lý như một sự cố quá tải.
2. **Đối chiếu với load test đã đo** (xem `load-tests/INGESTION_LOAD_TEST.md` và
   `load-tests/END_TO_END_LOAD_TEST.md`): ở mức 50 user/~127 req/s (ingestion riêng) và ~109 req/s
   (toàn pipeline), tỷ lệ lỗi đo được là 0%, P95 dưới 70ms, ngoại trừ vài request lệch tới ~2.1s do
   OpenSearch tự refresh (near-real-time, không phải lỗi) khi tải tăng đột ngột. Nếu production đang
   thấy lỗi thật (khác 0%) hoặc P95 vượt xa các mốc này, đó là dấu hiệu quá tải thật, không phải nhiễu.
3. **Chạy lại load test để xác nhận mức tải hiện tại** (phối hợp với Minh nếu nghi ngờ ở tầng
   `ingestion`, dùng `locust -f load-tests/locustfile.py IngestionUser` để cô lập, hoặc
   `END_TO_END_LOAD_TEST.md` bước "4b" để tái hiện cả pipeline) nhằm xác định mức tải nào bắt đầu gây
   lỗi/latency vượt ngưỡng chấp nhận được.
4. **Hướng xử lý theo nguyên nhân**:
   - OpenSearch là nút nghẽn (CPU/heap cao, `OPENSEARCH_JAVA_OPTS` trong
     `ingestion/docker-compose.yml` đang giới hạn `512m` cho dev) → tăng tài nguyên hoặc chuyển sang
     cluster nhiều node (ngoài phạm vi single-node dev hiện tại).
   - `RETENTION_DAYS`/`RETENTION_INTERVAL_HOURS` (xem `ingestion/README.md`) chưa chạy, index phình
     to dần làm chậm ghi/đọc → kiểm tra retention job có chạy đúng chu kỳ không, chạy thử
     `python -m ingestion.scripts.run_retention` thủ công nếu cần giải phóng ngay.
   - Nhiều instance `ingestion`/`query-api` cùng dùng `LOG_STORE_BACKEND=memory` (dev) ở các tiến
     trình khác nhau → mỗi tiến trình có bộ nhớ riêng, không thấy dữ liệu của nhau; đảm bảo môi
     trường thật luôn dùng `opensearch` (giá trị mặc định), không phải nguyên nhân quá tải nhưng là
     lỗi cấu hình dễ nhầm với "rớt log".

## Liên hệ

| Module | Phụ trách |
|---|---|
| Demo app / Fault injection | Mạnh |
| Ingestion / Storage | Minh |
| Clustering / Anomaly score / Alert | Nam |
| Search / Incident View / Tích hợp | Nghĩa |

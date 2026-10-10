# Clustering job nen (Nam) - image deploy, phan dong goi deploy cua Nghia.
#
# Khong phai HTTP service - chay vo han qua run_forever() (xem src/main.py).
# Build tu THU MUC GOC repo vi can ca package `ingestion` (doc log that qua
# ingestion.src.storage.get_store()) va docs/architect/contracts/ (ca
# log-schema.json qua ingestion, lan cluster-record.schema.json qua
# clustering/src/storage.py):
#   docker build -f clustering/Dockerfile -t log-anomaly-clustering .

FROM python:3.11-slim

WORKDIR /app

COPY clustering/requirements.txt clustering/requirements.txt
RUN pip install --no-cache-dir -r clustering/requirements.txt

COPY clustering clustering
COPY ingestion ingestion
COPY docs docs

ENV PYTHONPATH=/app
RUN useradd -m appuser && chown -R appuser /app
USER appuser

CMD ["python", "-m", "clustering.src.main"]

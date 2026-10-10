# Query & Incident API (Nghia) - image deploy, phan dong goi deploy cua Nghia.
#
# Build tu THU MUC GOC repo vi can ca package `ingestion` (LogStore) va
# `clustering` (ClusterStore) + docs/architect/contracts/ (ca 2 module do doc
# schema luc import, xem ingestion/src/validator.py va clustering/src/storage.py):
#   docker build -f query-api/Dockerfile -t log-anomaly-query-api .

FROM python:3.11-slim

WORKDIR /app

# query-api/requirements.txt chi co fastapi/uvicorn/httpx, nhung main.py import
# truc tiep ingestion.src.storage (can opensearch-py) va clustering.src.storage
# (can jsonschema + opensearch-py) - can ca clustering/requirements.txt de du
# dependency runtime cho 2 module do (xem ingestion/requirements.txt cung co
# opensearch-py nhung them apscheduler khong can thiet cho query-api).
COPY query-api/requirements.txt query-api/requirements.txt
COPY clustering/requirements.txt clustering/requirements.txt
RUN pip install --no-cache-dir -r query-api/requirements.txt -r clustering/requirements.txt

COPY query-api query-api
COPY ingestion ingestion
COPY clustering clustering
COPY docs docs

ENV PYTHONPATH=/app
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8002
CMD ["uvicorn", "query-api.src.main:app", "--host", "0.0.0.0", "--port", "8002"]

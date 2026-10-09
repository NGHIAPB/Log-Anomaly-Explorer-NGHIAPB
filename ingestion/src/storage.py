"""
Storage client cho log da chuan hoa.

Chon: OpenSearch - phu hop Search (MVP) nho full-text tren `message`, loc
chinh xac tren `service`/`trace_id`, va khong can license (khac Elasticsearch).

Giu interface duoi day on dinh de clustering (Nam) va query-api (Nghia)
khong bi anh huong khi doi engine luu tru. Ca hai module do nen import
`get_store()` o file nay thay vi tu khoi tao store rieng, de dung chung
MOT ket noi/cau hinh voi Ingestion.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Iterable

LOG_INDEX_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "log_id": {"type": "keyword"},
            "timestamp": {"type": "date"},
            "level": {"type": "keyword"},
            "service": {"type": "keyword"},
            "trace_id": {"type": "keyword"},
            "span_id": {"type": "keyword"},
            "request_id": {"type": "keyword"},
            "message": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 1024}},
            },
            "stack_trace": {"type": "text"},
            # "flat_object" (ten rieng cua OpenSearch, khac "flattened" cua Elasticsearch)
            # chap nhan object voi field bat ky (OTel metadata thay doi tuy service)
            # ma khong gay mapping explosion.
            "metadata": {"type": "flat_object"},
        }
    },
}

QUARANTINE_INDEX_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "received_at": {"type": "date"},
            # payload goc co the sai schema (thieu field, sai kieu) - dung flat_object
            # thay vi mapping chat de khong bi reject khi index.
            "payload": {"type": "flat_object"},
            "errors": {"type": "text"},
        }
    },
}


class LogStore:
    """Interface luu & truy van log. Cai dat cu the trong lop con."""

    def write_log(self, log_id: str, log: dict) -> None:
        raise NotImplementedError

    def write_quarantine(self, log: dict, errors: list[str]) -> None:
        """Log sai schema - luu rieng, KHONG vao index chinh (xem docs/architect/contracts/api-contract.md)."""
        raise NotImplementedError

    def search(self, *, service: str | None = None, trace_id: str | None = None,
               query: str | None = None, time_from: str | None = None,
               time_to: str | None = None, size: int = 200) -> list[dict]:
        """Dung boi Nghia (GET /search). Moi log tra ve kem `log_id`."""
        raise NotImplementedError

    def get_by_ids(self, log_ids: Iterable[str]) -> list[dict]:
        """Tra ve cac log theo `log_ids` cua mot ClusterRecord (xem
        cluster-record.schema.json). Dung boi Nghia cho Incident View
        (GET /clusters/{cluster_id}) va boi Nam de doc lai log goc."""
        raise NotImplementedError

    def delete_older_than(self, cutoff_iso: str) -> int:
        """Dung boi retention job (xem retention.py). Tra ve so log da xoa."""
        raise NotImplementedError


class InMemoryLogStore(LogStore):
    """Trien khai du phong (khong persist) de dev/test nhanh ma khong can
    dung OpenSearch that - bat bang `LOG_STORE_BACKEND=memory`. KHONG dung
    cho evidence/demo that (xem OpenSearchLogStore ben duoi).
    """

    def __init__(self) -> None:
        self._logs: dict[str, dict] = {}
        self._quarantine: list[dict] = []

    def write_log(self, log_id: str, log: dict) -> None:
        stored = dict(log)
        stored["log_id"] = log_id
        self._logs[log_id] = stored

    def write_quarantine(self, log: dict, errors: list[str]) -> None:
        self._quarantine.append({
            "received_at": datetime.now(timezone.utc).isoformat(),
            "payload": log,
            "errors": errors,
        })

    def search(self, **filters: Any) -> list[dict]:
        results = list(self._logs.values())
        if filters.get("service"):
            results = [l for l in results if l.get("service") == filters["service"]]
        if filters.get("trace_id"):
            results = [l for l in results if l.get("trace_id") == filters["trace_id"]]
        if filters.get("query"):
            q = filters["query"].lower()
            results = [l for l in results if q in l.get("message", "").lower()]
        if filters.get("time_from"):
            results = [l for l in results if l.get("timestamp", "") >= filters["time_from"]]
        if filters.get("time_to"):
            results = [l for l in results if l.get("timestamp", "") <= filters["time_to"]]
        results.sort(key=lambda l: l.get("timestamp", ""), reverse=True)
        size = filters.get("size") or 200
        return results[:size]

    def get_by_ids(self, log_ids: Iterable[str]) -> list[dict]:
        return [self._logs[i] for i in log_ids if i in self._logs]

    def delete_older_than(self, cutoff_iso: str) -> int:
        before = len(self._logs)
        self._logs = {k: v for k, v in self._logs.items() if v["timestamp"] >= cutoff_iso}
        return before - len(self._logs)


class OpenSearchLogStore(LogStore):
    """Trien khai that tren OpenSearch. Dung cho evidence/demo va la
    gia tri mac dinh cua `get_store()` (xem `docker-compose.yml` de chay
    OpenSearch single-node cuc bo)."""

    def __init__(
        self,
        hosts: list[str],
        index: str = "logs",
        quarantine_index: str = "logs-quarantine",
        http_auth: tuple[str, str] | None = None,
        use_ssl: bool = False,
        verify_certs: bool = False,
        timeout: float = 10.0,
    ) -> None:
        from opensearchpy import OpenSearch

        self._index = index
        self._quarantine_index = quarantine_index
        self._client = OpenSearch(
            hosts=hosts,
            http_auth=http_auth,
            use_ssl=use_ssl,
            verify_certs=verify_certs,
            timeout=timeout,
        )
        self._ensure_indices()

    def _ensure_indices(self) -> None:
        if not self._client.indices.exists(index=self._index):
            self._client.indices.create(index=self._index, body=LOG_INDEX_MAPPING)
        if not self._client.indices.exists(index=self._quarantine_index):
            self._client.indices.create(index=self._quarantine_index, body=QUARANTINE_INDEX_MAPPING)

    def write_log(self, log_id: str, log: dict) -> None:
        doc = dict(log)
        doc["log_id"] = log_id
        # refresh mac dinh (khong force): OpenSearch tu refresh ~1s/lan (near-real-time).
        # Force refresh tren moi write se giam throughput manh duoi tai (do tranh chap
        # index) ma search/clustering (job nen, khong phai real-time strict) khong can.
        self._client.index(index=self._index, id=log_id, body=doc)

    def write_quarantine(self, log: dict, errors: list[str]) -> None:
        doc = {
            "received_at": datetime.now(timezone.utc).isoformat(),
            "payload": log,
            "errors": errors,
        }
        self._client.index(index=self._quarantine_index, body=doc)

    def search(self, *, service: str | None = None, trace_id: str | None = None,
               query: str | None = None, time_from: str | None = None,
               time_to: str | None = None, size: int = 200) -> list[dict]:
        must: list[dict] = []
        if service:
            must.append({"term": {"service": service}})
        if trace_id:
            must.append({"term": {"trace_id": trace_id}})
        if query:
            must.append({"match": {"message": query}})
        time_range: dict[str, str] = {}
        if time_from:
            time_range["gte"] = time_from
        if time_to:
            time_range["lte"] = time_to
        if time_range:
            must.append({"range": {"timestamp": time_range}})

        body = {
            "query": {"bool": {"must": must}} if must else {"match_all": {}},
            "sort": [{"timestamp": {"order": "desc"}}],
            "size": size,
        }
        resp = self._client.search(index=self._index, body=body)
        return [hit["_source"] for hit in resp["hits"]["hits"]]

    def get_by_ids(self, log_ids: Iterable[str]) -> list[dict]:
        ids = [i for i in log_ids if i]
        if not ids:
            return []
        resp = self._client.mget(index=self._index, body={"ids": ids})
        return [doc["_source"] for doc in resp["docs"] if doc.get("found")]

    def delete_older_than(self, cutoff_iso: str) -> int:
        body = {"query": {"range": {"timestamp": {"lt": cutoff_iso}}}}
        resp = self._client.delete_by_query(index=self._index, body=body, refresh=True)
        return int(resp.get("deleted", 0))


def build_log_store() -> LogStore:
    """Tao LogStore theo cau hinh bien moi truong (xem ingestion/README.md):

    - LOG_STORE_BACKEND: "opensearch" (mac dinh, that) hoac "memory" (dev/test nhe,
      khong can chay OpenSearch).
    - OPENSEARCH_URL, OPENSEARCH_INDEX, OPENSEARCH_QUARANTINE_INDEX,
      OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD, OPENSEARCH_USE_SSL, OPENSEARCH_VERIFY_CERTS.
    """
    backend = os.environ.get("LOG_STORE_BACKEND", "opensearch").strip().lower()

    if backend == "memory":
        return InMemoryLogStore()

    if backend == "opensearch":
        url = os.environ.get("OPENSEARCH_URL", "http://localhost:9200")
        index = os.environ.get("OPENSEARCH_INDEX", "logs")
        quarantine_index = os.environ.get("OPENSEARCH_QUARANTINE_INDEX", "logs-quarantine")
        username = os.environ.get("OPENSEARCH_USERNAME")
        password = os.environ.get("OPENSEARCH_PASSWORD")
        http_auth = (username, password) if username and password else None
        use_ssl = os.environ.get("OPENSEARCH_USE_SSL", "false").strip().lower() == "true"
        verify_certs = os.environ.get("OPENSEARCH_VERIFY_CERTS", "false").strip().lower() == "true"
        return OpenSearchLogStore(
            hosts=[url],
            index=index,
            quarantine_index=quarantine_index,
            http_auth=http_auth,
            use_ssl=use_ssl,
            verify_certs=verify_certs,
        )

    raise ValueError(f"LOG_STORE_BACKEND khong hop le: {backend!r} (dung 'opensearch' hoac 'memory')")


_store_singleton: LogStore | None = None


def get_store() -> LogStore:
    """Store dung chung cho toan bo process. Clustering (Nam) va query-api
    (Nghia) nen import ham nay thay vi tu tao LogStore rieng, de dam bao
    doc/ghi cung mot noi voi Ingestion."""
    global _store_singleton
    if _store_singleton is None:
        _store_singleton = build_log_store()
    return _store_singleton

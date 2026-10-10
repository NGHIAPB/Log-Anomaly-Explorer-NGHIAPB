"""
Storage client cho ClusterRecord (cum loi + anomaly score).

Cung mo hinh voi `ingestion/src/storage.py` (Minh): mot interface on dinh
(`ClusterStore`) + 2 cach trien khai (OpenSearch cho that/demo, in-memory cho
dev/test nhe), chon qua bien moi truong, dung chung MOT ket noi qua
`get_cluster_store()`.

**Quan trong cho Nghia**: dung tu khoi tao ClusterStore rieng - import
`get_cluster_store()` o file nay, giong nhu cach Nam/Nghia da duoc yeu cau
dung `get_store()` cua Minh cho log:

    from clustering.src.storage import get_cluster_store

    cstore = get_cluster_store()
    clusters = cstore.list_clusters(status="alerted")      # GET /clusters
    cluster = cstore.get_cluster(cluster_id)                # GET /clusters/{id}
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft7Validator

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "architect"
    / "contracts"
    / "cluster-record.schema.json"
)
_schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
_validator = Draft7Validator(_schema)
_SCHEMA_FIELDS = tuple(_schema["properties"].keys())

CLUSTER_INDEX_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "cluster_id": {"type": "keyword"},
            "signature": {"type": "keyword"},
            "score": {"type": "double"},
            "log_ids": {"type": "keyword"},
            "trace_ids": {"type": "keyword"},
            "first_seen": {"type": "date"},
            "last_seen": {"type": "date"},
            "status": {"type": "keyword"},
        }
    },
}


def to_cluster_record(record: dict) -> dict:
    """Giu lai dung cac truong trong cluster-record.schema.json (additionalProperties:
    false) - loai bo cac truong noi bo nhu "service" (chi dung cho alert.py va
    precision_recall.py, xem anomaly_score.py)."""
    doc = {k: v for k, v in record.items() if k in _SCHEMA_FIELDS}
    errors = sorted(_validator.iter_errors(doc), key=lambda e: e.path)
    if errors:
        details = "; ".join(e.message for e in errors)
        raise ValueError(f"ClusterRecord khong khop cluster-record.schema.json: {details}")
    return doc


def _merge_cluster(existing: dict, new: dict) -> dict:
    """Mot signature xuat hien lai o khung thoi gian sau se cap nhat (khong
    tao moi) ClusterRecord da co cung cluster_id: gop log_ids/trace_ids,
    giu first_seen som nhat / last_seen muon nhat, nhung status/score lay
    theo lan tinh gan nhat (phan anh dung muc do bat thuong HIEN TAI)."""
    merged = dict(new)
    merged["log_ids"] = sorted(set(existing.get("log_ids", [])) | set(new.get("log_ids", [])))
    merged["trace_ids"] = sorted(set(existing.get("trace_ids", [])) | set(new.get("trace_ids", [])))
    merged["first_seen"] = min(existing.get("first_seen", new["first_seen"]), new["first_seen"])
    merged["last_seen"] = max(existing.get("last_seen", new["last_seen"]), new["last_seen"])
    return merged


class ClusterStore:
    """Interface luu & truy van ClusterRecord. Cai dat cu the trong lop con."""

    def write_cluster(self, record: dict) -> dict:
        """Ghi (upsert theo cluster_id) mot ClusterRecord. Neu da ton tai,
        gop voi ban ghi cu (xem `_merge_cluster`). Tra ve ban ghi da luu
        (sau khi gop, dung theo cluster-record.schema.json)."""
        raise NotImplementedError

    def get_cluster(self, cluster_id: str) -> dict | None:
        """Dung boi Nghia (GET /clusters/{cluster_id})."""
        raise NotImplementedError

    def list_clusters(self, *, status: str | None = None, since: str | None = None,
                       size: int = 200) -> list[dict]:
        """Dung boi Nghia (GET /clusters)."""
        raise NotImplementedError


class InMemoryClusterStore(ClusterStore):
    """Trien khai du phong (khong persist) de dev/test nhanh - bat bang
    `CLUSTER_STORE_BACKEND=memory`. KHONG dung cho evidence/demo that."""

    def __init__(self) -> None:
        self._clusters: dict[str, dict] = {}

    def write_cluster(self, record: dict) -> dict:
        doc = to_cluster_record(record)
        existing = self._clusters.get(doc["cluster_id"])
        if existing:
            doc = to_cluster_record(_merge_cluster(existing, doc))
        self._clusters[doc["cluster_id"]] = doc
        return doc

    def get_cluster(self, cluster_id: str) -> dict | None:
        return self._clusters.get(cluster_id)

    def list_clusters(self, *, status: str | None = None, since: str | None = None,
                       size: int = 200) -> list[dict]:
        results = list(self._clusters.values())
        if status:
            results = [c for c in results if c.get("status") == status]
        if since:
            results = [c for c in results if c.get("last_seen", "") >= since]
        results.sort(key=lambda c: c.get("last_seen", ""), reverse=True)
        return results[:size]


class OpenSearchClusterStore(ClusterStore):
    """Trien khai that tren OpenSearch - dung chung cluster (va co the dung
    chung ket noi) voi OpenSearch cua Ingestion (xem ingestion/docker-compose.yml),
    chi khac index. Day la gia tri mac dinh cua `get_cluster_store()`."""

    def __init__(
        self,
        hosts: list[str],
        index: str = "clusters",
        http_auth: tuple[str, str] | None = None,
        use_ssl: bool = False,
        verify_certs: bool = False,
        timeout: float = 10.0,
    ) -> None:
        from opensearchpy import OpenSearch

        self._index = index
        self._client = OpenSearch(
            hosts=hosts,
            http_auth=http_auth,
            use_ssl=use_ssl,
            verify_certs=verify_certs,
            timeout=timeout,
        )
        if not self._client.indices.exists(index=self._index):
            self._client.indices.create(index=self._index, body=CLUSTER_INDEX_MAPPING)

    def write_cluster(self, record: dict) -> dict:
        doc = to_cluster_record(record)
        existing = self.get_cluster(doc["cluster_id"])
        if existing:
            doc = to_cluster_record(_merge_cluster(existing, doc))
        self._client.index(index=self._index, id=doc["cluster_id"], body=doc, refresh=True)
        return doc

    def get_cluster(self, cluster_id: str) -> dict | None:
        try:
            resp = self._client.get(index=self._index, id=cluster_id)
        except Exception:
            return None
        return resp["_source"] if resp.get("found") else None

    def list_clusters(self, *, status: str | None = None, since: str | None = None,
                       size: int = 200) -> list[dict]:
        must: list[dict] = []
        if status:
            must.append({"term": {"status": status}})
        if since:
            must.append({"range": {"last_seen": {"gte": since}}})

        body = {
            "query": {"bool": {"must": must}} if must else {"match_all": {}},
            "sort": [{"last_seen": {"order": "desc"}}],
            "size": size,
        }
        resp = self._client.search(index=self._index, body=body)
        return [hit["_source"] for hit in resp["hits"]["hits"]]


def build_cluster_store() -> ClusterStore:
    """Tao ClusterStore theo bien moi truong (xem clustering/README.md):

    - CLUSTER_STORE_BACKEND: "opensearch" (mac dinh, that) hoac "memory" (dev/test nhe).
    - OPENSEARCH_URL (dung chung voi ingestion), OPENSEARCH_CLUSTER_INDEX,
      OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD, OPENSEARCH_USE_SSL, OPENSEARCH_VERIFY_CERTS.
    """
    backend = os.environ.get("CLUSTER_STORE_BACKEND", "opensearch").strip().lower()

    if backend == "memory":
        return InMemoryClusterStore()

    if backend == "opensearch":
        url = os.environ.get("OPENSEARCH_URL", "http://localhost:9200")
        index = os.environ.get("OPENSEARCH_CLUSTER_INDEX", "clusters")
        username = os.environ.get("OPENSEARCH_USERNAME")
        password = os.environ.get("OPENSEARCH_PASSWORD")
        http_auth = (username, password) if username and password else None
        use_ssl = os.environ.get("OPENSEARCH_USE_SSL", "false").strip().lower() == "true"
        verify_certs = os.environ.get("OPENSEARCH_VERIFY_CERTS", "false").strip().lower() == "true"
        return OpenSearchClusterStore(
            hosts=[url],
            index=index,
            http_auth=http_auth,
            use_ssl=use_ssl,
            verify_certs=verify_certs,
        )

    raise ValueError(f"CLUSTER_STORE_BACKEND khong hop le: {backend!r} (dung 'opensearch' hoac 'memory')")


_cluster_store_singleton: ClusterStore | None = None


def get_cluster_store() -> ClusterStore:
    """ClusterStore dung chung cho toan bo process. Nghia nen import ham nay
    thay vi tu tao ClusterStore rieng."""
    global _cluster_store_singleton
    if _cluster_store_singleton is None:
        _cluster_store_singleton = build_cluster_store()
    return _cluster_store_singleton

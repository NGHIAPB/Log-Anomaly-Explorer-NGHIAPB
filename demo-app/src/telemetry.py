"""
Cau hinh OpenTelemetry cho demo-app.

Phu trach: Manh.
Khoi tao TracerProvider that + exporter, va expose tracer/trace-context
de main.py gan trace_id/span_id thuc vao moi structured log.
"""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME as OTEL_SERVICE_NAME_KEY
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

_initialized = False


def setup_telemetry(service_name: str) -> None:
    """Khoi tao OpenTelemetry SDK cho service nay (idempotent).

    Neu bien moi truong OTEL_EXPORTER_OTLP_ENDPOINT duoc cau hinh, xuat span
    qua OTLP/HTTP toi collector do. Neu khong, fallback ve ConsoleSpanExporter
    de van quan sat duoc trace_id/span_id khi chay demo local khong co collector.
    """
    global _initialized
    if _initialized:
        return

    resource = Resource.create({OTEL_SERVICE_NAME_KEY: service_name})
    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint.rstrip('/')}/v1/traces")
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _initialized = True


def get_tracer(instrumenting_module_name: str = __name__):
    """Tracer dung de mo span cho moi request (xem middleware trong main.py)."""
    return trace.get_tracer(instrumenting_module_name)


def get_current_trace_context() -> dict:
    """Tra ve {"trace_id": ..., "span_id": ...} cua span dang active.

    Dung de dinh kem vao moi structured log truoc khi gui ve /ingest,
    dung theo docs/architect/contracts/log-schema.json. Can duoc goi trong
    luc mot span dang active (middleware trong main.py dam bao dieu nay
    cho moi request HTTP).
    """
    span_context = trace.get_current_span().get_span_context()
    if span_context is None or span_context.trace_id == 0:
        raise RuntimeError(
            "Khong co span OpenTelemetry dang active. Dam bao setup_telemetry() "
            "da duoc goi va request di qua tracing middleware trong main.py."
        )
    return {
        "trace_id": format(span_context.trace_id, "032x"),
        "span_id": format(span_context.span_id, "016x"),
    }

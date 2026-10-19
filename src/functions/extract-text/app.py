"""
extract-text step function for FunctionGraph.

Extracts text content from a document identified by doc_id.
This is a step handler for the durable-workflow-sample workflow.

Environment variables required:
  OBS_BUCKET_NAME - OBS bucket where documents are stored
  OTEL_SERVICE_NAME - Service name for OpenTelemetry
  OTEL_EXPORTER_OTLP_ENDPOINT - OTLP collector endpoint
"""

import os
import json
import time
import logging
from typing import Any

# OpenTelemetry - standard SDK, no vendor-specific plugin
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor

# Initialize logging FIRST so logger is ready for OTel instrumentation
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)
logger = logging.getLogger("extract-text")

# Initialize OpenTelemetry (standard OTel SDK, no ADOT layer needed)
_otel_initialized = False


def _init_otel():
    global _otel_initialized
    if _otel_initialized:
        return
    try:
        service_name = os.environ.get("OTEL_SERVICE_NAME", "extract-text-func")
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")

        resource = Resource(attributes={SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)

        if endpoint:
            exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)

        # Auto-instrument logging to stamp traceId/spanId on every log record
        LoggingInstrumentor().instrument(set_logging_format=True)

        logger.info(f"OpenTelemetry initialized (service={service_name}, endpoint={endpoint})")
    except Exception as e:
        logger.warning(f"OpenTelemetry initialization failed: {e}. Tracing disabled.")
    finally:
        _otel_initialized = True


_init_otel()
tracer = trace.get_tracer(__name__)


@tracer.start_as_current_span("extract-text")
def handler(event: dict, context: Any = None) -> dict:
    """
    FunctionGraph step handler for extract-text.

    Args:
        event: {
            "doc_id": "string",
            "workflow_execution_id": "string",   # Used as trace ID for correlation
            "step_name": "extract-text"
        }
        context: FunctionGraph context (optional)

    Returns:
        {
            "doc_id": "string",
            "text": "string",
            "workflow_execution_id": "string"
        }
    """
    doc_id = event.get("doc_id", "unknown")
    workflow_execution_id = event.get("workflow_execution_id", "")

    span = trace.get_current_span()
    span.set_attribute("doc_id", doc_id)
    span.set_attribute("workflow.execution_id", workflow_execution_id)
    span.set_attribute("workflow.step", "extract-text")

    logger.info(f"Extracting text from document: {doc_id}",
                extra={
                    "doc_id": doc_id,
                    "workflow_execution_id": workflow_execution_id,
                    "step": "extract-text"
                })

    # Simulate text extraction work (~1 second)
    time.sleep(1.0)

    # In a real implementation, this would read from OBS:
    # obs_client = ObsClient(access_key_id=os.environ["HW_ACCESS_KEY"],
    #                         secret_access_key=os.environ["HW_SECRET_KEY"],
    #                         server='obs.cn-north-4.myhuaweicloud.com')
    # response = obs_client.getObject(os.environ["OBS_BUCKET_NAME"], f"docs/{doc_id}.txt")

    result = {
        "doc_id": doc_id,
        "text": f"Extracted text content from document: {doc_id}",
        "workflow_execution_id": workflow_execution_id
    }

    logger.info(f"Text extraction complete for doc_id={doc_id}, text_length={len(result['text'])}",
                extra={"doc_id": doc_id, "text_length": len(result["text"])})

    return result

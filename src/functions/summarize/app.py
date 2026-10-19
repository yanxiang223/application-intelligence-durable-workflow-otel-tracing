"""
summarize step function for FunctionGraph.

Summarizes extracted text content.
This is a step handler for the durable-workflow-sample workflow.

Environment variables required:
  OTEL_SERVICE_NAME - Service name for OpenTelemetry
  OTEL_EXPORTER_OTLP_ENDPOINT - OTLP collector endpoint
"""

import os
import json
import time
import logging
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)
logger = logging.getLogger("summarize")

_otel_initialized = False


def _init_otel():
    global _otel_initialized
    if _otel_initialized:
        return
    try:
        service_name = os.environ.get("OTEL_SERVICE_NAME", "summarize-func")
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")

        resource = Resource(attributes={SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)

        if endpoint:
            exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        LoggingInstrumentor().instrument(set_logging_format=True)

        logger.info(f"OpenTelemetry initialized (service={service_name})")
    except Exception as e:
        logger.warning(f"OpenTelemetry initialization failed: {e}")
    finally:
        _otel_initialized = True


_init_otel()
tracer = trace.get_tracer(__name__)


@tracer.start_as_current_span("summarize")
def handler(event: dict, context: Any = None) -> dict:
    """
    FunctionGraph step handler for summarize.

    Args:
        event: {
            "doc_id": "string",
            "text": "string",
            "workflow_execution_id": "string"
        }
        context: FunctionGraph context (optional)

    Returns:
        {
            "doc_id": "string",
            "summary": "string",
            "workflow_execution_id": "string"
        }
    """
    doc_id = event.get("doc_id", "unknown")
    text = event.get("text", "")
    workflow_execution_id = event.get("workflow_execution_id", "")

    span = trace.get_current_span()
    span.set_attribute("doc_id", doc_id)
    span.set_attribute("workflow.execution_id", workflow_execution_id)
    span.set_attribute("workflow.step", "summarize")
    span.set_attribute("input.text_length", len(text))

    logger.info(f"Summarizing document: {doc_id}, text_length={len(text)}",
                extra={
                    "doc_id": doc_id,
                    "text_length": len(text),
                    "workflow_execution_id": workflow_execution_id,
                    "step": "summarize"
                })

    # Simulate summarization work (~2 seconds)
    time.sleep(2.0)

    # In a real implementation, this would call a model endpoint:
    # summary = call_model_endpoint(text, model="pangu-summary-v1")

    summary = f"Summary of document {doc_id}: This is a simulated summary of text containing {len(text)} characters."

    result = {
        "doc_id": doc_id,
        "summary": summary,
        "workflow_execution_id": workflow_execution_id
    }

    logger.info(f"Summarization complete for doc_id={doc_id}, summary_length={len(summary)}")

    return result

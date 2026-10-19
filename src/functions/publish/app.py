"""
publish step function for FunctionGraph.

Publishes the summarized document if approved by the reviewer.
This is a step handler for the durable-workflow-sample workflow.

Environment variables required:
  OBS_BUCKET_NAME - OBS bucket for published content
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
logger = logging.getLogger("publish")

_otel_initialized = False


def _init_otel():
    global _otel_initialized
    if _otel_initialized:
        return
    try:
        service_name = os.environ.get("OTEL_SERVICE_NAME", "publish-func")
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


@tracer.start_as_current_span("publish")
def handler(event: dict, context: Any = None) -> dict:
    """
    FunctionGraph step handler for publish.

    Args:
        event: {
            "doc_id": "string",
            "summary": "string",
            "approval": {
                "approved": bool,
                "reviewer": "string",
                "feedback": "string"
            },
            "workflow_execution_id": "string"
        }
        context: FunctionGraph context (optional)

    Returns:
        {
            "doc_id": "string",
            "status": "published" | "rejected",
            "reviewer": "string",
            "workflow_execution_id": "string"
        }
    """
    doc_id = event.get("doc_id", "unknown")
    summary = event.get("summary", "")
    approval = event.get("approval", {})
    workflow_execution_id = event.get("workflow_execution_id", "")

    span = trace.get_current_span()
    span.set_attribute("doc_id", doc_id)
    span.set_attribute("workflow.execution_id", workflow_execution_id)
    span.set_attribute("workflow.step", "publish")

    approved = approval.get("approved", False)
    reviewer = approval.get("reviewer", "unknown")
    feedback = approval.get("feedback", "")

    span.set_attribute("review.approved", approved)
    span.set_attribute("reviewer", reviewer)

    if not approved:
        logger.warning(
            f"Publishing rejected by reviewer: {reviewer}",
            extra={
                "doc_id": doc_id,
                "approved": approved,
                "reviewer": reviewer,
                "feedback": feedback,
                "workflow_execution_id": workflow_execution_id,
                "step": "publish"
            }
        )
        return {
            "doc_id": doc_id,
            "status": "rejected",
            "reviewer": reviewer,
            "feedback": feedback,
            "workflow_execution_id": workflow_execution_id
        }

    logger.info(
        f"Publishing with approval from: {reviewer}",
        extra={
            "doc_id": doc_id,
            "reviewer": reviewer,
            "feedback": feedback,
            "workflow_execution_id": workflow_execution_id,
            "step": "publish"
        }
    )

    # Simulate publishing work (~0.5 seconds)
    time.sleep(0.5)

    # In a real implementation, this would write to OBS:
    # obs_client = ObsClient(access_key_id=os.environ["HW_ACCESS_KEY"],
    #                         secret_access_key=os.environ["HW_SECRET_KEY"],
    #                         server='obs.cn-north-4.myhuaweicloud.com')
    # published_key = f"published/{doc_id}/summary.txt"
    # obs_client.putContent(os.environ["OBS_BUCKET_NAME"], published_key, summary)

    result = {
        "doc_id": doc_id,
        "status": "published",
        "reviewer": reviewer,
        "published_key": f"published/{doc_id}/summary.txt",
        "workflow_execution_id": workflow_execution_id
    }

    logger.info(f"Document {doc_id} published successfully by {reviewer}",
                extra={"doc_id": doc_id, "reviewer": reviewer})

    return result

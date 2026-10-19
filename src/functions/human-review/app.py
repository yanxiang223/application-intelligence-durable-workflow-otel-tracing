"""
human-review step function for FunctionGraph.

Implements the wait-for-callback state for the durable workflow.
The workflow suspends at this step and waits for an external callback
containing the reviewer's approval/rejection decision.

Workflow callback mechanism:
  - FunctionGraph workflow exposes a callback_uri when it reaches this step
  - External reviewer POSTs to that URI with approval details
  - Workflow resumes with the callback payload as input

Environment variables required:
  OTEL_SERVICE_NAME - Service name for OpenTelemetry
  OTEL_EXPORTER_OTLP_ENDPOINT - OTLP collector endpoint
"""

import os
import json
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
logger = logging.getLogger("human-review")

_otel_initialized = False


def _init_otel():
    global _otel_initialized
    if _otel_initialized:
        return
    try:
        service_name = os.environ.get("OTEL_SERVICE_NAME", "human-review-func")
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


@tracer.start_as_current_span("human-review")
def handler(event: dict, context: Any = None) -> dict:
    """
    FunctionGraph step handler for human-review.

    In the FunctionGraph workflow model, this step is defined as a 'Wait' state.
    The workflow engine suspends execution and waits for an external callback.
    When the callback arrives, the workflow resumes with the callback payload.

    The callback payload is expected to contain:
      {
        "approved": true/false,
        "reviewer": "string",
        "feedback": "string" (optional)
      }

    Args:
        event: {
            "doc_id": "string",
            "summary": "string",
            "workflow_execution_id": "string",
            "callback_id": "string",        # Provided by FunctionGraph workflow engine
            "callback_uri": "string",       # Provided by FunctionGraph workflow engine
            "approved": true/false,         # Present when callback has been received
            "reviewer": "string",           # Present when callback has been received
            "feedback": "string"           # Present when callback has been received
          }
        context: FunctionGraph context (optional)

    Returns:
        {
            "doc_id": "string",
            "summary": "string",
            "approval": {
                "approved": bool,
                "reviewer": "string",
                "feedback": "string"
            },
            "workflow_execution_id": "string"
        }
    """
    doc_id = event.get("doc_id", "unknown")
    summary = event.get("summary", "")
    workflow_execution_id = event.get("workflow_execution_id", "")
    callback_id = event.get("callback_id", "")
    callback_uri = event.get("callback_uri", "")

    span = trace.get_current_span()
    span.set_attribute("doc_id", doc_id)
    span.set_attribute("workflow.execution_id", workflow_execution_id)
    span.set_attribute("workflow.step", "human-review")
    span.set_attribute("callback_id", callback_id)

    # Check if callback has been received (workflow resumed with approval data)
    approved = event.get("approved")
    reviewer = event.get("reviewer", "")
    feedback = event.get("feedback", "")

    if approved is not None:
        # Callback received — workflow has resumed
        logger.info(
            f"Human review callback received: approved={approved}, reviewer={reviewer}",
            extra={
                "doc_id": doc_id,
                "approved": approved,
                "reviewer": reviewer,
                "feedback": feedback,
                "workflow_execution_id": workflow_execution_id,
                "step": "human-review"
            }
        )
        span.set_attribute("review.approved", approved)
        span.set_attribute("reviewer", reviewer)

        return {
            "doc_id": doc_id,
            "summary": summary,
            "approval": {
                "approved": approved,
                "reviewer": reviewer,
                "feedback": feedback
            },
            "workflow_execution_id": workflow_execution_id
        }
    else:
        # Callback not yet received — this is the initial pass
        # The workflow engine will suspend at this step and wait for callback
        logger.info(
            f"Human review step reached, workflow waiting for callback. "
            f"callback_id={callback_id}, callback_uri={callback_uri}",
            extra={
                "doc_id": doc_id,
                "callback_id": callback_id,
                "callback_uri": callback_uri,
                "workflow_execution_id": workflow_execution_id,
                "step": "human-review"
            }
        )

        # The FunctionGraph workflow engine handles the suspension.
        # We raise a special marker so the engine knows to wait for callback.
        # On Huawei Cloud FunctionGraph, the 'Wait' state type handles this automatically.
        # This function returns the waiting state info; the workflow engine suspends.
        return {
            "doc_id": doc_id,
            "summary": summary,
            "workflow_execution_id": workflow_execution_id,
            "callback_id": callback_id,
            "callback_uri": callback_uri,
            "status": "WAITING_FOR_CALLBACK",
            "instructions": (
                f"To resume this workflow, send a POST request to: {callback_uri} "
                f"with body: {{\"approved\": true, \"reviewer\": \"<name>\", \"feedback\": \"<notes>\"}}"
            )
        }

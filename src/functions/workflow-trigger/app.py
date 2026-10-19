"""
workflow-trigger: Entry point function for the durable workflow sample.

This function is invoked via HTTP (APIG trigger) and starts the
FunctionGraph workflow execution. It demonstrates how to pass the
workflow execution ID to downstream steps for unified trace correlation.

Environment variables required:
  WORKFLOW_URI - FunctionGraph workflow URI (e.g., "workflows/xxxxx")
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
logger = logging.getLogger("workflow-trigger")

_otel_initialized = False


def _init_otel():
    global _otel_initialized
    if _otel_initialized:
        return
    try:
        service_name = os.environ.get("OTEL_SERVICE_NAME", "workflow-trigger")
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


@tracer.start_as_current_span("workflow-trigger")
def handler(event: dict, context: Any = None) -> dict:
    """
    HTTP entry point for the durable workflow.

    Expected event (HTTP body JSON):
      {
        "doc_id": "string"
      }

    Returns:
      {
        "execution_id": "string",
        "workflow_uri": "string",
        "status": "RUNNING",
        "started_at": "ISO8601 timestamp"
      }
    """
    doc_id = event.get("doc_id", "test-doc-001")

    span = trace.get_current_span()
    span.set_attribute("doc_id", doc_id)

    logger.info(f"Starting durable workflow for doc_id={doc_id}",
                extra={"doc_id": doc_id, "step": "workflow-trigger"})

    # Get workflow URI from environment
    workflow_uri = os.environ.get("WORKFLOW_URI", "")
    if not workflow_uri:
        logger.error("WORKFLOW_URI environment variable not set")
        return {
            "error": "WORKFLOW_URI not configured",
            "status": "FAILED"
        }

    # Use standard HTTP client (urllib or requests) to call FunctionGraph workflow API
    # This replaces the cloud SDK call pattern
    import urllib.request
    import urllib.parse

    region = os.environ.get("HW_REGION", "cn-north-4")
    project_id = os.environ.get("HW_PROJECT_ID", "")

    # FunctionGraph workflow execution API
    # POST https://functiongraph.{region}.myhuaweicloud.com/v1/functiongraph/workflows/{workflow_uri}/executions
    api_url = f"https://functiongraph.{region}.myhuaweicloud.com/v1/functiongraph/workflows/{workflow_uri}/executions"

    # Build the initial input that will be passed to the first step
    workflow_input = {
        "doc_id": doc_id,
        "workflow_execution_id": "",  # Will be filled by the workflow engine
        "step": "workflow-trigger"
    }

    payload = json.dumps({"input": workflow_input}).encode("utf-8")

    # Build the request with Huawei Cloud IAM authentication
    # Using simplified IAM token approach (production should use signed requests)
    iam_token = os.environ.get("HW_IAM_TOKEN", "")

    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Workflow-Execution-Id": f"exec-{doc_id}-{os.urandom(4).hex()}"
        },
        method="POST"
    )

    if iam_token:
        req.add_header("X-Auth-Token", iam_token)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result_body = json.loads(response.read().decode("utf-8"))
            execution_id = result_body.get("execution_id", "")
            workflow_execution_id = execution_id

            # Update span with execution ID
            span.set_attribute("workflow.execution_id", workflow_execution_id)
            span.set_attribute("workflow.uri", workflow_uri)

            logger.info(
                f"Workflow execution started: execution_id={execution_id}",
                extra={
                    "doc_id": doc_id,
                    "execution_id": execution_id,
                    "workflow_uri": workflow_uri
                }
            )

            return {
                "execution_id": execution_id,
                "workflow_uri": workflow_uri,
                "status": result_body.get("status", "RUNNING"),
                "started_at": result_body.get("created_time", ""),
                "doc_id": doc_id
            }

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        logger.error(f"Failed to start workflow: {e.code} {error_body}")
        return {
            "error": f"HTTP {e.code}: {error_body}",
            "status": "FAILED"
        }
    except Exception as e:
        logger.error(f"Failed to start workflow: {e}")
        return {
            "error": str(e),
            "status": "FAILED"
        }

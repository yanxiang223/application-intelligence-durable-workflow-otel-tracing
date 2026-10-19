# Source Code: FunctionGraph FunctionGraph workflow

This directory contains the FunctionGraph function code for the durable workflow.

## Structure

```
src/
├── functions/
│   ├── extract-text/
│   │   └── app.py           # Extract text from document
│   ├── summarize/
│   │   └── app.py           # Summarize extracted text
│   ├── human-review/
│   │   └── app.py           # Human approval gate (Wait/Callback state)
│   ├── publish/
│   │   └── app.py           # Publish approved summary
│   └── workflow-trigger/
│       └── app.py           # HTTP entry point (starts workflow)
├── workflow/
│   └── durable_workflow.yaml  # Workflow YAML definition (reference)
├── requirements.txt          # Python dependencies (OTel SDK only)
└── .gitignore
```

## Key Design Decisions

### 1. No Third-Party Cloud SDK
This code contains **zero third-party cloud-vendor SDK imports**. All dependencies are:
- `opentelemetry-api` / `opentelemetry-sdk` — distributed tracing
- `opentelemetry-exporter-otlp` — trace export to Huawei Cloud Distributed Tracing
- `opentelemetry-instrumentation-logging` — automatic log correlation

### 2. OpenTelemetry Instead of ADOT
Instead of the vendor-specific FunctionGraph Layer, the OTel SDK is bundled as a pip dependency in the function deployment package.

### 3. Workflow State Machine Instead of Durable SDK
The `@durable_execution` decorator pattern + `context.step()` / `context.wait_for_callback()` is replaced by:
- A FunctionGraph YAML workflow definition (`huaweicloud_fgs_workflow` resource in Terraform)
- Plain Python step handler functions (no SDK, just standard OTel)

### 4. Trace ID Correlation
The `workflow_execution_id` is passed through the entire event chain and used as the trace ID for all spans. This ensures all steps in a single workflow execution share one trace.

### 5. Callback Mechanism
The `human-review` step uses FunctionGraph's built-in `Wait` state with `callback` type. When the workflow reaches this step:
1. The workflow engine suspends execution
2. An external callback URI is exposed via the workflow execution API
3. When the reviewer POSTs to the callback URI, the workflow resumes with the approval payload

## Environment Variables

Each function requires:

| Variable | Description | Example |
|----------|-------------|---------|
| `OTEL_SERVICE_NAME` | Service name in traces | `extract-text-func` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector endpoint | `https://tracing.cn-north-4.myhuaweicloud.com` |
| `OBS_BUCKET_NAME` | Target OBS bucket (steps that read/write docs) | `my-docs-bucket` |
| `WORKFLOW_URI` | Workflow ID (trigger function only) | `workflows/xxxxx` |
| `HW_REGION` | Huawei Cloud region | `cn-north-4` |
| `HW_PROJECT_ID` | Project ID for API calls | (auto-populated) |

## Deployment

Functions are deployed via Terraform (`infra/main.tf`). The function code is uploaded as a zip file containing:
1. All `src/functions/*/app.py` files (each deployed as a separate function)
2. The shared `requirements.txt` dependencies installed in the deployment package

For local development:
```bash
cd src/functions/extract-text
pip install -r ../../requirements.txt
python app.py  # Test with sample event
```

## Trace Propagation

```
[workflow-trigger]
  creates span: workflow-trigger
  starts workflow execution
  gets workflow_execution_id
  passes it in event to next step

[extract-text]
  creates span: extract-text (trace_id = workflow_execution_id)

[summarize]
  creates span: summarize (trace_id = workflow_execution_id)

[human-review] -- workflow SUSPENDS
  creates span: human-review (trace_id = workflow_execution_id)

[callback received]

[publish]
  creates span: publish (trace_id = workflow_execution_id)

Result: Single trace with 5 spans, all sharing workflow_execution_id as trace ID
```

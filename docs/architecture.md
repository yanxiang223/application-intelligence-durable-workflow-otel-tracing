# Architecture: Durable Workflow with Distributed Tracing on Huawei Cloud

## Overview

This solution deploys a **document-review workflow** on Huawei Cloud using FunctionGraph (serverless workflow orchestration) instrumented with OpenTelemetry. The workflow spans multiple function invocations with a human-approval gate, unified under a single distributed trace.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Huawei Cloud Region                               │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                   FunctionGraph Workflow                              │   │
│  │  ┌──────────┐   ┌──────────┐   ┌───────────┐   ┌──────────┐         │   │
│  │  │extract-  │──▶│summarize │──▶│human-     │──▶│publish  │         │   │
│  │  │text step │   │  step    │   │review(Wai │   │  step    │         │   │
│  │  │(Python)  │   │(Python)  │   │t/Calback) │   │(Python)  │         │   │
│  │  └────┬─────┘   └────┬─────┘   └─────┬─────┘   └────┬─────┘         │   │
│  │       │              │               │              │                 │   │
│  │       └──────────────┴───────────────┴──────────────┘                 │   │
│  │              (Workflow State Machine: YAML Definition)                 │   │
│  └──────────────────────────┬───────────────────────────────────────────┘   │
│                              │                                                 │
│         ┌────────────────────┼────────────────────┐                         │
│         │                    │                    │                         │
│         ▼                    ▼                    ▼                         │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐                  │
│  │  extract_   │      │  summarize_ │      │   publish_  │                  │
│  │   text_     │      │   func      │      │   func      │                  │
│  │   func      │      │             │      │             │                  │
│  │(FGS Func)   │      │(FGS Func)   │      │(FGS Func)   │                  │
│  └──────┬──────┘      └──────┬──────┘      └──────┬──────┘                  │
│         │                    │                    │                          │
│         └────────────────────┴────────────────────┘                          │
│                              │                                                 │
│                              ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              OpenTelemetry SDK (bundled in each function)             │   │
│  │  - Trace context propagation (W3C Trace Context / traceparent)       │   │
│  │  - Span per workflow step                                             │   │
│  │  - Log correlation (traceId, spanId on every log record)              │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                              │
│         ┌─────────────────────┼─────────────────────┐                     │
│         │ OTLP Exporter       │                     │                     │
│         ▼                     ▼                     ▼                     │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐               │
│  │ Distributed │      │      LTS     │      │   OBS       │               │
│  │  Tracing     │      │ (Log Tank   │      │ (Document   │               │
│  │  Service     │      │  Service)   │      │  Storage)   │               │
│  └─────────────┘      └─────────────┘      └─────────────┘               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                        ▲
                                        │
                         ┌──────────────┴──────────────┐
                         │    External Callback         │
                         │    (Reviewer Approval)       │
                         │    POST /workflows/...       │
                         │    /callbacks/{callback_id}  │
                         └──────────────────────────────┘
```

## Workflow Steps

| Step | Name | Duration | Description |
|------|------|----------|-------------|
| 1 | `extract-text` | ~1s | Extract text content from the input document |
| 2 | `summarize` | ~2s | Generate a summary of the extracted text |
| 3 | `human-review` | Wait/Callback | Workflow suspends, waiting for external approval callback |
| 4 | `publish` | ~0.5s | Publish the summary if approved; reject if not |

## Components

### FunctionGraph Workflow

The workflow is defined in `workflow.yaml` using the FunctionGraph workflow DSL. It defines:
- **States**: `extract-text` (Pass) → `summarize` (Pass) → `human-review` (Wait/Callback) → `publish` (Pass)
- **Transitions**: Linear step progression with conditional branching on approval
- **Callback**: The `human-review` step waits for an external callback via the FunctionGraph callback API

### FunctionGraph Functions (Step Handlers)

Each workflow step maps to a separate FunctionGraph function:

| Function | Purpose |
|----------|---------|
| `extract-text-func` | Reads document, extracts text (simulated) |
| `summarize-func` | Processes extracted text into summary (simulated) |
| `publish-func` | Publishes summary if approved |
| `workflow-trigger` | Entry point; starts the workflow execution |

### OpenTelemetry Instrumentation

Each function is instrumented with the **standard OpenTelemetry Python SDK** (no Huawei-specific OTel plugin needed):

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

# Initialize OTel
resource = Resource(attributes={SERVICE_NAME: "durable-workflow-sample"})
provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(OTLPSpanExporter(
    endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
    insecure=True
))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)
```

**Key capabilities:**
- **Single trace per workflow execution**: The workflow execution ID is used as the trace ID, spanning all step functions
- **Span per operation**: Each `step` call creates a child span
- **Log correlation**: The OTel `LoggingInstrumentor` automatically stamps every log record with `traceId` and `spanId`
- **W3C Trace Context propagation**: `traceparent` header propagates context across function invocations

### Distributed Tracing Service

Huawei Cloud's **Distributed Tracing Service** collects and visualizes traces:
- Accepts OTLP (OpenTelemetry Protocol) exported traces
- Console UI for trace timeline and span inspection
- Trace-level metrics (latency, error rates)

### LTS (Log Tank Service)

All function logs flow to **LTS** with trace correlation:
- Logs are automatically stamped with `traceId`, `spanId` by the OTel LoggingInstrumentor
- Log query by trace ID in the LTS console
- Retention and archiving policies configurable per log group

## Infrastructure

| Resource | Huawei Cloud Resource Type | Purpose |
|----------|---------------------------|---------|
| Workflow | `huaweicloud_fgs_workflow` | Workflow state machine definition |
| Workflow Steps | `huaweicloud_fgs_function` (x4) | Per-step Python functions |
| Function Agency | `huaweicloud_identity_agency` | Function execution permissions |
| OBS Bucket | `huaweicloud_obs_bucket` | Document storage (input/output) |
| VPC | `huaweicloud_vpc` + `huaweicloud_vpc_subnet` | Network isolation (optional) |

## Trace Flow

```
1. Client invokes workflow-trigger function
       ↓
2. workflow-trigger starts the workflow execution
       ↓
3. Step 1 (extract-text) executes → span "extract-text" created
       ↓
4. Step 2 (summarize) executes → span "summarize" created
       ↓
5. Step 3 (human-review) → workflow SUSPENDS, callback URI exposed
       ↓
6. External reviewer POSTs to callback URI with approval
       ↓
7. Workflow RESUMES → Step 4 (publish) executes → span "publish" created
       ↓
8. Single trace ID spans ALL steps (1-4) and both invocations
```

## Design Highlights

| 能力 | 华为云实现 |
|------|-----------|
| 持久化编排 SDK | FunctionGraph 原生工作流（YAML 状态机），无需第三方编排 SDK |
| 追踪插件 | 标准 OpenTelemetry SDK（厂商中立），随函数打包 |
| 追踪 ID 派生 | W3C Trace Context（`traceparent`） |
| 回调机制 | FunctionGraph 工作流 Callback REST API |
| 打包机制 | OTel SDK 直接打包进函数部署包 |

---

*Document version: 1.0*
*Target region: cn-north-4*

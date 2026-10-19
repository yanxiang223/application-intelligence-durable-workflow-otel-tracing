# Durable Workflow with Distributed Tracing on Huawei Cloud

[![License: MIT-0](https://img.shields.io/badge/License-MIT--0-blue.svg)](https://github.com/huaweicloud-samples/application-intelligence-durable-workflow-otel-tracing/blob/master/LICENSE)
![Huawei Cloud](https://img.shields.io/badge/Platform-Huawei%20Cloud-orange)
![Region: cn-north-4](https://img.shields.io/badge/Region-cn--north--4-green)

A minimal, deployable sample that instruments a **FunctionGraph durable workflow** with **OpenTelemetry**, demonstrating unified distributed tracing across multiple function invocations with per-step spans and automatically correlated logs.
---

## 1. Overview

This solution deploys a document-review workflow with a human-approval gate:

```
extract-text (~1s) → summarize (~2s) → human-review (wait for callback) → publish (~0.5s)
```

The workflow uses **FunctionGraph** (Huawei Cloud's serverless workflow orchestration) and **OpenTelemetry** for unified distributed tracing. The workflow spans at least two function invocations: the first runs `extract-text` and `summarize`, then suspends at `human-review` (zero compute cost while waiting); when the callback arrives, the workflow resumes and runs `publish`. With OpenTelemetry instrumentation, all steps appear under a **single unified trace** with per-step spans.

---

## 2. Architecture

```
+-------------------------------------------------------------------------+
|                     Huawei Cloud Architecture                           |
|        FunctionGraph Durable Workflow + OpenTelemetry Tracing          |
+-------------------------------------------------------------------------+

   +--------------+     +--------------------------------------------------+
   |   Client    |---->|           FunctionGraph Workflow                |
   +--------------+     |  +------------+   +----------+   +----------+  |
                       |  |   trigger  |--->|  extract |--->| summarize|  |
                       |  +------------+   +----------+   +----------+  |
                       |                             |                    |
                       |                      +----------+             |
                       |                      |human-    |             |
                       |                      |review    |             |
                       |                      |(WAIT)    |             |
                       |                      +----+-----+             |
                       |                           |                   |
                       |                      +----------+             |
                       |                      |  publish |             |
                       |                      +----------+             |
                       +-----------------------+----------------------------------+
                                               |
                                       +--------+--------+
                                       |  External   |
                                       |  Callback   |
                                       |(Approval/   |
                                       | Human Review)|
                                       +--------------+

+-------------------------------------------------------------------------+
|                        Observability Layer                              |
|  +---------------------+   +-----------------+   +-----------------+  |
|  |  Distributed       |   |      LTS        |   |      OBS        |  |
|  |  Tracing Service   |<--|  (Correlated   |   |  (Document     |  |
|  |  (OTLP Collector)  |   |   Logs)        |   |   Storage)     |  |
|  +---------------------+   +-----------------+   +-----------------+  |
+-------------------------------------------------------------------------+
```

**Key components:**
- **FunctionGraph Workflow**: YAML-based state machine orchestration with wait/callback states
- **FunctionGraph workflow**: Python functions for each workflow step (`trigger`, `extract`, `summarize`, `human-review`, `publish`)
- **OpenTelemetry SDK**: Standard OTel Python SDK — bundled in function deployment package (no FunctionGraph Layer equivalent)
- **Distributed Tracing Service**: Trace collection and visualization via OTLP protocol
- **LTS (Log Tank Service)**: Correlated log collection with automatic `traceId`/`spanId` stamping

See [docs/architecture.md](docs/architecture.md) for full architecture details.

---

## 3. Key Features

| Feature | Description |
|---------|-------------|
| **Unified distributed trace** | Single trace ID spans all workflow steps across multiple invocations |
| **Per-step spans** | Each `extract-text`, `summarize`, `publish` operation is its own span |
| **Log correlation** | Every log record is automatically stamped with `traceId` and `spanId` |
| **Human-approval gate** | Workflow suspends at `human-review` step, waits for external callback |
| **Zero-cost wait** | No compute is consumed while the workflow is suspended (callback-driven) |
| **Standard OTel SDK** | Uses the vendor-neutral OpenTelemetry Python SDK — no Huawei-specific plugin needed |

---

## 4. Huawei Cloud Services Used

| Service | Purpose | 
|---------|---------|
| FunctionGraph | Serverless workflow + functions | 
| Distributed Tracing Service | OTel trace collection & visualization | 
| LTS (Log Tank Service) | Log collection with trace correlation | 
| OBS (Object Storage Service) | Document storage (input/output) | 

---

## 5. Prerequisites

- **Python >= 3.11**
- **Terraform >= 1.5.0**
- **Huawei Cloud account** with access to **cn-north-4** region
- **Access Key ID & Secret Access Key** from [Huawei Cloud IAM](https://console-intl.myhuaweicloud.com/iam/)

---

## 6. Quick Start

### 6.1 Clone the Repository

```bash
git clone https://github.com/huaweicloud-samples/application-intelligence-durable-workflow-otel-tracing.git
cd application-intelligence-durable-workflow-otel-tracing
```

### 6.2 Configure Credentials

```bash
export HW_ACCESS_KEY="<YOUR_ACCESS_KEY>"
export HW_SECRET_KEY="<YOUR_SECRET_KEY>"
export HW_REGION="cn-north-4"
```

### 6.3 Deploy with Terraform

```bash
cd infra
terraform init
terraform plan
terraform apply
```

Type `yes` when prompted. Deployment takes ~5-10 minutes.

### 6.4 Get the Trigger URL

```bash
terraform output workflow_trigger_url
```

### 6.5 Trigger the Workflow

```bash
curl -X POST "<WORKFLOW_TRIGGER_URL>" \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "test-doc-001"}'
```

### 6.6 Submit the Callback (Approval)

Find the callback URI from the workflow execution details in the console, then:

```bash
curl -X POST "<CALLBACK_URI>" \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "reviewer": "alice"}'
```

### 6.7 View Traces

1. Go to **Distributed Tracing Service** in the Huawei Cloud console (cn-north-4)
2. Select the time range
3. Search by `workflow_execution_id` or `doc_id`

---

## 7. Project Structure

```
application-intelligence-durable-workflow-otel-tracing/
├── docs/
│   ├── architecture.md      # Huawei Cloud architecture details
│   └── deployment-guide.md  # Step-by-step deployment instructions
├── infra/
│   ├── main.tf              # Terraform: functions, workflow, OBS, agency
│   ├── variables.tf         # Terraform variables
│   ├── outputs.tf           # Terraform outputs (trigger URL, etc.)
│   └── terraform.tfvars     # (create this) — your credentials
├── src/
│   ├── extract_text/        # extract-text step function
│   │   ├── index.py
│   │   └── requirements.txt
│   ├── summarize/          # summarize step function
│   │   ├── index.py
│   │   └── requirements.txt
│   ├── publish/            # publish step function
│   │   ├── index.py
│   │   └── requirements.txt
│   ├── workflow_trigger/  # Entry point function
│   │   ├── index.py
│   │   └── requirements.txt
│   └── workflow.yaml       # FunctionGraph workflow definition
├── others/
│   ├── analysis.md          # Phase 1 analysis output
│   ├── service-mapping.md  # service mapping
│   └── migration-report.md  # Migration feasibility report
└── README.md
```

---

## 8. Workflow Definition (workflow.yaml)

```yaml
workflow:
  name: durable-workflow-sample
  runtime: python3.11

start_state: extract_text

states:
  extract_text:
    type: Pass
    next: summarize
    comment: "Extract text from input document"

  summarize:
    type: Pass
    next: human_review
    comment: "Summarize the extracted text"

  human_review:
    type: Wait
    callback:
      method: POST
    next: publish_decision
    comment: "Wait for human approval callback"

  publish_decision:
    type: Choice
    choices:
      - condition: "$.approved == true"
        next: publish
      - condition: "$.approved == false"
        next: rejected
    default: rejected

  publish:
    type: Pass
    end: true
    comment: "Publish the summary (approved path)"

  rejected:
    type: Pass
    end: true
    comment: "Workflow rejected by reviewer"
```

---

## 9. OpenTelemetry Instrumentation

Each step function uses the **standard OpenTelemetry Python SDK** (no Huawei-specific plugin):

```python
# requirements.txt
opentelemetry-api>=1.25.0
opentelemetry-sdk>=1.25.0
opentelemetry-exporter-otlp>=1.25.0
opentelemetry-instrumentation-logging>=0.46b0
```

```python
# index.py (each step function)
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
import os, logging

# Initialize OTel
resource = Resource(attributes={SERVICE_NAME: os.environ["OTEL_SERVICE_NAME"]})
provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(
    OTLPSpanExporter(
        endpoint=os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"],
        insecure=True
    )
))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

@tracer.start_as_current_span("extract-text")
def extract_text(doc_id: str, span=None):
    logger.info(f"Extracting text from document: {doc_id}",
                extra={"traceId": span.context.trace_id})
    return {"doc_id": doc_id, "text": "extracted content"}
```

---

## 10. Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OTEL_SERVICE_NAME` | Service name in traces | `durable-workflow-sample` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector endpoint | `https://tracing.cn-north-4.myhuaweicloud.com` |
| `OBS_BUCKET_NAME` | Target OBS bucket | `durable-workflow-docs-cn-north-4` |
| `WORKFLOW_URI` | Workflow identifier | `workflows/xxxxx` |

---

## 11. Cleanup

Destroy all resources to avoid ongoing charges:

```bash
cd infra
terraform destroy
```

---

## 12. FAQ

**Q: Why use FunctionGraph instead of raw serverless functions?**
A: The original sample uses durable workflow for stateful, multi-invocation workflows. FunctionGraph is Huawei Cloud's equivalent service for stateful serverless orchestration — it natively supports wait/callback states, step progression, and execution history.

**Q: Why bundle the OTel SDK instead of using a FunctionGraph layer?**
A: Huawei Cloud does not have a FunctionGraph Layer equivalent. The OpenTelemetry SDK must be bundled in the function deployment package as a pip dependency.

**Q: How does the trace ID get propagated across steps?**
A: The workflow execution ID is used as the trace ID. Each step function receives the `workflow_execution_id` in its input event and uses it to initialize the OTel span context, ensuring all spans share one trace.

**Q: What happens if the callback never comes?**
A: The workflow remains in `WAITING` state indefinitely. You can abort it via the FunctionGraph console or API. There is no charge for the waiting state (no compute is consumed).

---

## 13. References

- [FunctionGraph Documentation](https://console-intl.myhuaweicloud.com/functiongraph/)
- [OpenTelemetry Python SDK](https://opentelemetry.io/docs/instrumentation/python/)
- [Distributed Tracing Service](https://console-intl.myhuaweicloud.com/dts/)
- [LTS - Log Tank Service](https://console-intl.myhuaweicloud.com/lts/)
- [Terraform Huawei Cloud Provider](https://registry.terraform.io/providers/huaweicloud/huaweicloud/latest/docs)

---

## 14. Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines.

---

## 15. License

This sample is licensed under the **MIT-0 License**. See the [LICENSE](../LICENSE) file.

---

## 16. Acknowledgments


---

## 17. Contact

| Item | Value |
|---|---|
| **Created by** |
| **Maintained by** | 
| **Contact** | GitHub Issues 

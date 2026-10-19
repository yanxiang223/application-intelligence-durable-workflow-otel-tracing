# Deployment Guide: Durable Workflow with Distributed Tracing on Huawei Cloud

## Prerequisites

### 1. Environment Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | >= 3.11 | Used for step function handlers |
| Terraform | >= 1.5.0 | For infrastructure provisioning |
| Huawei Cloud CLI | Latest | For manual verification (optional) |
| Git | Any recent version | For cloning source |

### 2. Huawei Cloud Account & Permissions

You need an Huawei Cloud account with the following permissions in **cn-north-4** region:

| Service | Permission | Purpose |
|---------|-----------|---------|
| FunctionGraph | Full access | Create/update functions, workflows, triggers |
| OBS | Full access | Store documents and workflow artifacts |
| Distributed Tracing | Full access | Query traces after deployment |
| LTS | Full access | View correlated logs |
| IAM | Agency management | Create function execution agencies |

### 3. AK/SK Configuration

Obtain your Access Key ID and Secret Access Key from the [Huawei Cloud My Credentials](https://console-intl.myhuaweicloud.com/iam/) page.

Set environment variables (do NOT hardcode in any file):

```bash
export HW_ACCESS_KEY="<YOUR_ACCESS_KEY>"
export HW_SECRET_KEY="<YOUR_SECRET_KEY>"
export HW_REGION="cn-north-4"
```

### 4. OpenTelemetry Endpoint

Before deploying, identify your OTLP endpoint for the Distributed Tracing Service in cn-north-4. This will be set as an environment variable in the Terraform configuration.

---

## Quick Start (One-Command Deploy)

```bash
cd infra && terraform init && terraform plan && terraform apply
```

**Expected output:**
```
Apply complete! Resources: 8 added, 0 changed, 0 destroyed.

Outputs:
workflow_trigger_url = "https://functiongraph.cn-north-4.myhuaweicloud.com/v1/functiongraph/functions/<func_urn>/invoke"
workflow_callback_url = "https://functiongraph.cn-north-4.myhuaweicloud.com/v1/functiongraph/workflows/<workflow_uri>/callbacks/<callback_id>"
```

---

## Step-by-Step Deployment

### Step 1: Clone and Setup

```bash
# Clone the repository
git clone https://github.com/huaweicloud-samples/application-intelligence-durable-workflow-otel-tracing.git
cd application-intelligence-durable-workflow-otel-tracing

# Navigate to infrastructure directory
cd infra
```

### Step 2: Configure Terraform Variables

Create a `terraform.tfvars` file (do NOT commit this file):

```hcl
hw_access_key = "<YOUR_ACCESS_KEY>"
hw_secret_key = "<YOUR_SECRET_KEY>"
hw_region     = "cn-north-4"

# OBS bucket name for document storage (must be globally unique)
bucket_name = "durable-workflow-docs-<your-name>-cn-north-4"

# FunctionGraph workspace (usually "default")
workspace = "default"

# Tags
tags = {
  project     = "durable-workflow-otel"
  environment = "demo"
  owner       = "<your-name>"
}
```

### Step 3: Initialize Terraform

```bash
terraform init
```

**Expected output:**
```
Initializing the backend...
Initializing provider plugins...
- Finding huaweicloud versions matching "~> 1.61"...
- Installing huaweicloud v1.61.0...
Terraform has been successfully initialized!
```

### Step 4: Plan (Dry Run)

```bash
terraform plan
```

**Expected output:** Terraform will list all resources to be created. Verify the following are included:
- 4x FunctionGraph functions (extract-text, summarize, publish, workflow-trigger)
- 1x FunctionGraph workflow
- 1x OBS bucket
- 1x IAM agency
- 1x VPC (optional, for private deployment)

### Step 5: Apply (Create Resources)

```bash
terraform apply
```

Type `yes` when prompted.

**Resources created:**

| Resource Type | Count | Description |
|--------------|-------|-------------|
| `huaweicloud_fgs_function` | 4 | Step handler functions |
| `huaweicloud_fgs_workflow` | 1 | Workflow state machine |
| `huaweicloud_fgs_trigger` | 1 | HTTP trigger for workflow-trigger function |
| `huaweicloud_obs_bucket` | 1 | Document storage |
| `huaweicloud_identity_agency` | 1 | Function execution permissions |

**Time estimate:** ~5-10 minutes for all resources.

### Step 6: Verify Deployment

#### 6a. Check Function Status

```bash
# List all functions
hcloud functiongraph list-functions --region cn-north-4
# Or via Huawei Cloud console: FunctionGraph > Functions
```

Functions should show status `Active`.

#### 6b. Check Workflow Status

```bash
# Via Huawei Cloud console: FunctionGraph > Workflows
# Verify workflow state is "Published" and version is "$latest"
```

#### 6c. Get the Trigger URL

```bash
terraform output workflow_trigger_url
```

---

## Usage

### Trigger the Workflow

Invoke the workflow by sending an HTTP POST to the trigger URL:

```bash
curl -X POST "<WORKFLOW_TRIGGER_URL>" \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "test-doc-001"}'
```

**Response:**
```json
{
  "execution_id": "32014b3a-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "workflow_uri": "workflows/xxxxx",
  "status": "RUNNING",
  "started_at": "2026-08-14T12:00:00Z"
}
```

### Wait for Human Review Callback

The workflow will suspend at the `human-review` step. The callback URI is exposed in the workflow execution state.

**Find the callback URI** (from workflow execution details in the console or API):
```
https://functiongraph.cn-north-4.myhuaweicloud.com/v1/functiongraph/workflows/<workflow_uri>/callbacks/<callback_id>
```

### Submit Approval Callback

From an external system (reviewer's approval service):

```bash
curl -X POST "<CALLBACK_URI>" \
  -H "Content-Type: application/json" \
  -d '{
    "approved": true,
    "reviewer": "alice",
    "feedback": "Looks good, approved for publication"
  }'
```

**Success response:**
```json
{
  "result": "continued",
  "execution_id": "32014b3a-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

### Verify Workflow Completion

```bash
# Check workflow execution status via API or console
# Status should show "Succeeded" after callback is received
```

---

## Verifying Distributed Tracing

### View Traces

1. Navigate to **Distributed Tracing Service** in the Huawei Cloud console (cn-north-4)
2. Select the time range (e.g., last 15 minutes)
3. Find the trace by execution ID (search by `workflow_execution_id` tag)

**Expected trace structure:**
```
[Workflow Execution: test-doc-001]
  ├── [Span: extract-text]          (~1s)
  ├── [Span: summarize]             (~2s)
  ├── [Span: human-review:wait]     (paused, duration = callback delay)
  └── [Span: publish]               (~0.5s)
```

**Verification criteria:**
- ✅ **Single trace ID** spans all 4 steps (both function invocations in the original design map to a single trace here via workflow execution ID)
- ✅ **Per-step spans**: Each workflow step has its own span
- ✅ **Wall-clock duration** includes the wait time between steps (human-review wait)
- ✅ **No duplicate spans** for completed steps (each step fires exactly once)

### View Correlated Logs

1. Navigate to **LTS (Log Tank Service)** in the console
2. Select the log group for FunctionGraph (`/FunctionGraph/durable-workflow/`)
3. Query by `traceId` to see all logs for a specific workflow execution

**Expected log structure:**
```json
{
  "level": "INFO",
  "message": "Extracting text from document: test-doc-001",
  "traceId": "4bf2a3c4d5e6f7a8b9c0d1e2f3a4b5c6",
  "spanId": "a1b2c3d4e5f6g7h8",
  "workflow_execution_id": "32014b3a-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

---

## Cleanup

Destroy all resources to avoid ongoing charges:

```bash
cd infra
terraform destroy
```

Type `yes` when prompted.

**Resources destroyed:**
- All FunctionGraph functions and workflows
- OBS bucket (will be emptied then deleted)
- IAM agency
- VPC resources (if created)

**Time estimate:** ~3-5 minutes.

---

## Troubleshooting

### Function Invocation Fails

1. **Check function logs:** LTS > Log Groups > `/FunctionGraph/<function-name>`
2. **Common cause:** Missing OBS bucket permissions — verify the function agency has OBS access
3. **Timeout:** Increase function timeout in `huaweicloud_fgs_function` resource (max 900s)

### Workflow Stuck in WAITING State

1. **Expected behavior:** The `human-review` step is designed to wait for a callback — this is correct
2. **If you want to cancel:** Use the workflow abort API:
   ```bash
   curl -X DELETE "https://functiongraph.cn-north-4.myhuaweicloud.com/v1/functiongraph/workflows/<workflow_uri>/executions/<execution_id>"
   ```

### No Traces in Distributed Tracing Console

1. **Verify OTel endpoint:** Ensure `OTEL_EXPORTER_OTLP_ENDPOINT` is correctly set in function environment variables
2. **Check network:** Functions must be able to reach the OTLP endpoint (check VPC/subnet configuration)
3. **Check trace ID:** Verify logs contain `traceId` (OTel SDK should auto-stamp)
4. **Propagation delay:** Traces may take up to 30s to appear after generation

### Terraform Apply Fails

1. **Authentication error:** Verify `HW_ACCESS_KEY` / `HW_SECRET_KEY` are correct
2. **Region not available:** Ensure `cn-north-4` is the correct region code
3. **Resource already exists:** Run `terraform plan` first to see existing state

---

## Configuration Reference

### Environment Variables (Set in Terraform)

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `OTEL_SERVICE_NAME` | Service name for traces | `durable-workflow-sample` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector endpoint | `https://tracing.cn-north-4.myhuaweicloud.com` |
| `OBS_BUCKET_NAME` | Target OBS bucket | `durable-workflow-docs-cn-north-4` |
| `WORKFLOW_REGION` | Region identifier | `cn-north-4` |

### Terraform Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `hw_access_key` | required | Huawei Cloud Access Key ID |
| `hw_secret_key` | required | Huawei Cloud Secret Access Key |
| `hw_region` | `cn-north-4` | Target region |
| `workspace` | `default` | FunctionGraph workspace |
| `bucket_name` | required | OBS bucket name (must be unique) |
| `tags` | `{}` | Resource tags |

---

*Document version: 1.0*
*Last updated: 2026-08-14*

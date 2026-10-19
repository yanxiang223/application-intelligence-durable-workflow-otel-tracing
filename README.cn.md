# 华为云持久工作流与分布式追踪

[![License: MIT-0](https://img.shields.io/badge/License-MIT--0-blue.svg)](https://github.com/huaweicloud-samples/application-intelligence-durable-workflow-otel-tracing/blob/master/LICENSE)
![Huawei Cloud](https://img.shields.io/badge/Platform-Huawei%20Cloud-orange)
![Region: cn-north-4](https://img.shields.io/badge/Region-cn--north--4-green)

一个最小化、可部署的示例，演示如何为 **FunctionGraph 持久工作流** 集成 **OpenTelemetry**，展示跨多次函数调用的统一分布式追踪，包含每步骤Span和自动关联的日志。

---

## 1. 概述

本解决方案部署了一个带人工审批关卡的文档审核工作流：

```
extract-text (~1s) → summarize (~2s) → human-review (等待回调) → publish (~0.5s)
```

工作流使用 **FunctionGraph**（华为云无服务器工作流编排）和 **OpenTelemetry** 实现统一分布式追踪。工作流至少跨越两次函数调用：第一次运行 `extract-text` 和 `summarize`，然后在 `human-review` 处挂起（挂起期间零计算成本）；回调到达后，工作流恢复并运行 `publish`。通过 OpenTelemetry instrumentation，所有步骤在**单一统一追踪**中呈现，每个步骤都有独立的 Span。

---

## 2. 架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     华为云架构                                     │
│         FunctionGraph 持久工作流 + OpenTelemetry 分布式追踪            │
└─────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐     ┌──────────────────────────────────────────────────┐
  │   客户端     │────▶│           FunctionGraph 工作流                   │
  └──────────────┘     │  ┌────────────┐   ┌──────────┐   ┌──────────┐  │
                        │  │   触发器   │──▶│  extract  │──▶│ summarize │  │
                        │  └────────────┘   └──────────┘   └──────────┘  │
                        │                              │                   │
                        │                       ┌──────────┐            │
                        │                       │human-     │            │
                        │                       │review     │            │
                        │                       │(等待回调)  │            │
                        │                       └────┬─────┘            │
                        │                            │                 │
                        │                       ┌──────────┐            │
                        │                       │  publish │            │
                        │                       └──────────┘            │
                        └────────────────────┬──────────────────────────────────┘
                                             │
                                    ┌────────┴────────┐
                                    │   外部回调      │
                                    │ (审批/人工介入) │
                                    └─────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────┐
  │                      观测层                                         │
  │  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐ │
  │  │  分布式追踪服务   │   │      LTS        │   │      OBS        │ │
  │  │  (OTLP 采集)   │◀──│  (关联日志)     │   │  (文档存储)     │ │
  │  └─────────────────┘   └─────────────────┘   └─────────────────┘ │
  └─────────────────────────────────────────────────────────────────────────┘
```

**核心组件：**
- **FunctionGraph Workflow**：基于 YAML 的状态机编排
- **FunctionGraph workflow**：每个工作流步骤的 Python 函数
- **OpenTelemetry SDK**：标准 OTel Python SDK（打包在函数中，非 Layer）
- **分布式追踪服务**：追踪采集与可视化（OTLP）
- **LTS（日志服务）**：带追踪 ID 标记的关联日志采集

详见 [docs/architecture.md](docs/architecture.md)。

---

## 3. 核心特性

| 特性 | 描述 |
|---|---|
| **统一分布式追踪** | 单一 trace ID 跨越多次调用的所有工作流步骤 |
| **每步骤 Span** | 每个 `extract-text`、`summarize`、`publish` 操作都有独立的 Span |
| **日志关联** | 每条日志记录自动标记 `traceId` 和 `spanId` |
| **人工审批关卡** | 工作流在 `human-review` 步骤挂起，等待外部回调 |
| **零成本等待** | 工作流挂起期间不消耗计算资源（回调驱动） |
| **标准 OTel SDK** | 使用供应商中立的 OpenTelemetry Python SDK — 无需华为特定插件 |

---

## 4. 使用的华为云服务

| 服务 | 用途 | 计费说明 |
|---|---|---|
| FunctionGraph | 无服务器工作流 + 函数 | 
| 分布式追踪服务 | OTel 追踪采集与可视化 | 
| LTS（日志服务） | 带追踪关联的日志采集 | 
| OBS（对象存储服务） | 文档存储（输入/输出） | 

---

## 5. 前置条件

- **Python >= 3.11**
- **Terraform >= 1.5.0**
- 可访问 **cn-north-4** 区域的**华为云账号**
- 来自[华为云 IAM](https://console-intl.myhuaweicloud.com/iam/)的**访问密钥 ID 与访问密钥**

---

## 6. 快速开始

### 6.1 克隆仓库

```bash
git clone https://github.com/huaweicloud-samples/application-intelligence-durable-workflow-otel-tracing.git
cd application-intelligence-durable-workflow-otel-tracing
```

### 6.2 配置凭据

```bash
export HW_ACCESS_KEY="<您的访问密钥>"
export HW_SECRET_KEY="<您的密钥>"
export HW_REGION="cn-north-4"
```

### 6.3 使用 Terraform 部署

```bash
cd infra
terraform init
terraform plan
terraform apply
```

输入 `yes` 确认。部署约需 5-10 分钟。

### 6.4 获取触发 URL

```bash
terraform output workflow_trigger_url
```

### 6.5 触发工作流

```bash
curl -X POST "<工作流触发URL>" \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "test-doc-001"}'
```

### 6.6 提交回调（审批）

从控制台的工作流执行详情中找到回调 URI，然后：

```bash
curl -X POST "<回调URI>" \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "reviewer": "alice"}'
```

### 6.7 查看追踪

1. 在华为云控制台进入**分布式追踪服务**（cn-north-4）
2. 选择时间范围
3. 按 `workflow_execution_id` 或 `doc_id` 搜索

---

## 7. 项目结构

```
application-intelligence-durable-workflow-otel-tracing/
├── docs/
│   ├── architecture.md      # 华为云架构详情
│   └── deployment-guide.md  # 分步部署说明
├── infra/
│   ├── main.tf              # Terraform：函数、工作流、OBS、委托
│   ├── variables.tf         # Terraform 变量
│   ├── outputs.tf           # Terraform 输出（触发 URL 等）
│   └── terraform.tfvars     #（需创建）— 您的凭据
├── src/
│   ├── extract_text/        # extract-text 步骤函数
│   │   ├── index.py
│   │   └── requirements.txt
│   ├── summarize/          # summarize 步骤函数
│   │   ├── index.py
│   │   └── requirements.txt
│   ├── publish            # publish 步骤函数
│   │   ├── index.py
│   │   └── requirements.txt
│   ├── workflow_trigger/  # 入口点函数
│   │   ├── index.py
│   │   └── requirements.txt
│   └── workflow.yaml       # FunctionGraph 工作流定义
├── others/
│   ├── analysis.md         # 阶段一分析输出
│   ├── service-mapping.md  # 服务映射
│   └── migration-report.md  # 迁移可行性报告
└── README.md
```

---

## 8. 工作流定义（workflow.yaml）

```yaml
workflow:
  name: durable-workflow-sample
  runtime: python3.11

start_state: extract_text

states:
  extract_text:
    type: Pass
    next: summarize
    comment: "从输入文档提取文本"

  summarize:
    type: Pass
    next: human_review
    comment: "汇总提取的文本"

  human_review:
    type: Wait
    callback:
      method: POST
    next: publish_decision
    comment: "等待人工审批回调"

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
    comment: "发布审批通过的摘要"

  rejected:
    type: Pass
    end: true
    comment: "工作流被审批人拒绝"
```

---

## 9. OpenTelemetry Instrumention

每个步骤函数使用**标准 OpenTelemetry Python SDK**（非华为特定插件）：

```python
# requirements.txt
opentelemetry-api>=1.25.0
opentelemetry-sdk>=1.25.0
opentelemetry-exporter-otlp>=1.25.0
opentelemetry-instrumentation-logging>=0.46b0
```

```python
# index.py（每个步骤函数）
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
import os, logging

# 初始化 OTel
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
    logger.info(f"正在提取文档文本: {doc_id}",
                extra={"traceId": span.context.trace_id})
    return {"doc_id": doc_id, "text": "提取的内容"}
```

---

## 10. 配置

### 环境变量

| 变量 | 描述 | 示例 |
|---|---|---|
| `OTEL_SERVICE_NAME` | 追踪中的服务名 | `durable-workflow-sample` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP 采集器端点 | `https://tracing.cn-north-4.myhuaweicloud.com` |
| `OBS_BUCKET_NAME` | 目标 OBS 桶 | `durable-workflow-docs-cn-north-4` |
| `WORKFLOW_URI` | 工作流标识符 | `workflows/xxxxx` |

---

## 11. 清理

销毁所有资源以避免持续计费：

```bash
cd infra
terraform destroy
```

---

## 12. 常见问题

**Q: 为什么要用 FunctionGraph 而不是原始的无服务器函数？**
A: 原始示例使用 durable workflow 实现有状态的多调用工作流。FunctionGraph 是华为云等价的服务，支持有状态无服务器编排 — 原生支持 wait/callback 状态、步骤推进和执行历史。

**Q: 为什么要打包 OTel SDK 而不是使用 FunctionGraph Layer？**
A: 华为云没有 FunctionGraph Layer 等价物。OpenTelemetry SDK 必须作为 pip 依赖打包在函数部署包中。

**Q: 追踪 ID 如何在步骤间传播？**
A: 使用工作流执行 ID 作为追踪 ID。每个步骤函数在其输入事件中接收 `workflow_execution_id`，并用它初始化 OTel Span 上下文，确保所有 Span 共享同一追踪。

**Q: 如果回调永远不到会怎样？**
A: 工作流将无限期保持在 `WAITING` 状态。您可以通过 FunctionGraph 控制台或 API 中止它。挂起状态不收费（不消耗计算资源）。

---

## 13. 参考资料

- [FunctionGraph 文档](https://console-intl.myhuaweicloud.com/functiongraph/)
- [OpenTelemetry Python SDK](https://opentelemetry.io/docs/instrumentation/python/)
- [分布式追踪服务](https://console-intl.myhuaweicloud.com/dts/)
- [LTS - 日志服务](https://console-intl.myhuaweicloud.com/lts/)
- [Terraform 华为云 Provider](https://registry.terraform.io/providers/huaweicloud/huaweicloud/latest/docs)

---

## 14. 贡献指南

详见 [CONTRIBUTING.md](../CONTRIBUTING.md)。

---

## 15. 许可证

本示例采用 **MIT-0 许可证**。详见 [LICENSE](../LICENSE) 文件。

---

## 16. 致谢


---

## 17. 联系方式

| **创建者** |
| **维护者** |
| **联系方式** | GitHub Issues 
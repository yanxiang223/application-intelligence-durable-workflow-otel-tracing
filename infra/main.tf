# ============================================================
# main.tf - Durable Workflow Sample on Huawei Cloud
# 架构: 4x FunctionGraph 函数 + APIG 触发
#   (注: FGS Workflow/状态机暂不支持Terraform，需控制台手动创建)
# ============================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "~> 1.61"
    }
  }
}

provider "huaweicloud" {
  access_key = var.hw_access_key
  secret_key = var.hw_secret_key
  region     = var.hw_region
}

# ============================================================
# Data Sources
# ============================================================

data "huaweicloud_identity_projects" "current" {
  name = var.hw_region
}

# ============================================================
# OBS Bucket
# ============================================================

resource "huaweicloud_obs_bucket" "documents" {
  bucket        = var.bucket_name
  storage_class = "STANDARD"

  tags = merge(var.tags, {
    ManagedBy = "Terraform"
    Component  = "document-storage"
  })
}

# ============================================================
# IAM Agency (FunctionGraph 执行权限)
# ============================================================

#resource "huaweicloud_iam_agency" "fgs_execution" {
#  name                   = "durable-workflow-fgs-agency"
#  delegated_service_name = "functiongraph.myhuaweicloud.com"
#  description            = "FunctionGraph 执行权限"
#  duration               = "365"
#}
#
# ============================================================
# LTS Log Group
# ============================================================

resource "huaweicloud_lts_group" "functiongraph_logs" {
  group_name  = "durable-workflow-logs"
  ttl_in_days = 7
}

resource "huaweicloud_lts_stream" "extract_text_log" {
  group_id    = huaweicloud_lts_group.functiongraph_logs.id
  stream_name = "extract-text-func"
}

resource "huaweicloud_lts_stream" "summarize_log" {
  group_id    = huaweicloud_lts_group.functiongraph_logs.id
  stream_name = "summarize-func"
}

resource "huaweicloud_lts_stream" "human_review_log" {
  group_id    = huaweicloud_lts_group.functiongraph_logs.id
  stream_name = "human-review-func"
}

resource "huaweicloud_lts_stream" "publish_log" {
  group_id    = huaweicloud_lts_group.functiongraph_logs.id
  stream_name = "publish-func"
}

resource "huaweicloud_lts_stream" "workflow_trigger_log" {
  group_id    = huaweicloud_lts_group.functiongraph_logs.id
  stream_name = "workflow-trigger"
}

# ============================================================
# FunctionGraph: Extract-Text Function
# ============================================================

resource "huaweicloud_fgs_function" "extract_text" {
  name        = "extract-text-func"
  # agency      = huaweicloud_iam_agency.fgs_execution.id  # 暂时禁用: IAM Agency 委托格式需工单确认
  memory_size = var.function_memory_size
  timeout     = var.function_timeout
  runtime     = "Python3.9"
  handler     = "app.handler"
  code_type       = "zip"
  app         = var.workspace
  description = "Extract text from document (step 1)"
  log_stream_name = "extract-text-func"
  log_group_id    = huaweicloud_lts_group.functiongraph_logs.id
  enable_lts_log  = true

  # 修复 LTS 依赖顺序问题 - 确保日志流创建完成后再创建函数
  depends_on = [
    huaweicloud_lts_stream.extract_text_log,
    huaweicloud_lts_stream.workflow_trigger_log
  ]

  user_data = jsonencode({
    OTEL_SERVICE_NAME           = "extract-text-func"
    OTEL_EXPORTER_OTLP_ENDPOINT = var.otel_endpoint != "" ? var.otel_endpoint : "https://tracing.${var.hw_region}.myhuaweicloud.com"
    OBS_BUCKET_NAME            = huaweicloud_obs_bucket.documents.bucket
    HW_REGION                  = var.hw_region
    HW_PROJECT_ID             = data.huaweicloud_identity_projects.current.id
  })

  tags = merge(var.tags, {
    Component = "workflow-step"
    Step      = "extract-text"
  })
}

# ============================================================
# FunctionGraph: Summarize Function
# ============================================================

resource "huaweicloud_fgs_function" "summarize" {
  name        = "summarize-func"
  # agency      = huaweicloud_iam_agency.fgs_execution.id  # 暂时禁用: IAM Agency 委托格式需工单确认
  memory_size = var.function_memory_size
  timeout     = var.function_timeout
  runtime     = "Python3.9"
  handler     = "app.handler"
  code_type       = "zip"
  app         = var.workspace
  description = "Summarize extracted text (step 2)"
  log_stream_name = "summarize-func"
  log_group_id    = huaweicloud_lts_group.functiongraph_logs.id
  enable_lts_log  = true

  # 修复 LTS 依赖顺序问题 - 确保日志流创建完成后再创建函数
  depends_on = [
    huaweicloud_lts_stream.summarize_log
  ]

  user_data = jsonencode({
    OTEL_SERVICE_NAME           = "summarize-func"
    OTEL_EXPORTER_OTLP_ENDPOINT = var.otel_endpoint != "" ? var.otel_endpoint : "https://tracing.${var.hw_region}.myhuaweicloud.com"
    HW_REGION                   = var.hw_region
    HW_PROJECT_ID              = data.huaweicloud_identity_projects.current.id
  })

  tags = merge(var.tags, {
    Component = "workflow-step"
    Step      = "summarize"
  })
}

# ============================================================
# FunctionGraph: Human-Review Function
# ============================================================

resource "huaweicloud_fgs_function" "human_review" {
  name        = "human-review-func"
  # agency      = huaweicloud_iam_agency.fgs_execution.id  # 暂时禁用: IAM Agency 委托格式需工单确认
  memory_size = var.function_memory_size
  timeout     = 900
  runtime     = "Python3.9"
  handler     = "app.handler"
  code_type       = "zip"
  app         = var.workspace
  description = "Human review approval gate (step 3)"
  log_stream_name = "human-review-func"
  log_group_id    = huaweicloud_lts_group.functiongraph_logs.id
  enable_lts_log  = true

  # 修复 LTS 依赖顺序问题 - 确保日志流创建完成后再创建函数
  depends_on = [
    huaweicloud_lts_stream.human_review_log
  ]

  user_data = jsonencode({
    OTEL_SERVICE_NAME           = "human-review-func"
    OTEL_EXPORTER_OTLP_ENDPOINT = var.otel_endpoint != "" ? var.otel_endpoint : "https://tracing.${var.hw_region}.myhuaweicloud.com"
    HW_REGION                   = var.hw_region
    HW_PROJECT_ID              = data.huaweicloud_identity_projects.current.id
  })

  tags = merge(var.tags, {
    Component = "workflow-step"
    Step      = "human-review"
  })
}

# ============================================================
# FunctionGraph: Publish Function
# ============================================================

resource "huaweicloud_fgs_function" "publish" {
  name        = "publish-func"
  # agency      = huaweicloud_iam_agency.fgs_execution.id  # 暂时禁用: IAM Agency 委托格式需工单确认
  memory_size = var.function_memory_size
  timeout     = var.function_timeout
  runtime     = "Python3.9"
  handler     = "app.handler"
  code_type       = "zip"
  app         = var.workspace
  description = "Publish approved summary (step 4)"
  log_stream_name = "publish-func"
  log_group_id    = huaweicloud_lts_group.functiongraph_logs.id
  enable_lts_log  = true

  # 修复 LTS 依赖顺序问题 - 确保日志流创建完成后再创建函数
  depends_on = [
    huaweicloud_lts_stream.publish_log
  ]

  user_data = jsonencode({
    OTEL_SERVICE_NAME           = "publish-func"
    OTEL_EXPORTER_OTLP_ENDPOINT = var.otel_endpoint != "" ? var.otel_endpoint : "https://tracing.${var.hw_region}.myhuaweicloud.com"
    OBS_BUCKET_NAME             = huaweicloud_obs_bucket.documents.bucket
    HW_REGION                   = var.hw_region
    HW_PROJECT_ID              = data.huaweicloud_identity_projects.current.id
  })

  tags = merge(var.tags, {
    Component = "workflow-step"
    Step      = "publish"
  })
}

# ============================================================
# FunctionGraph: Workflow Trigger Function
# ============================================================

resource "huaweicloud_fgs_function" "workflow_trigger" {
  name        = "workflow-trigger"
  # agency      = huaweicloud_iam_agency.fgs_execution.id  # 暂时禁用: IAM Agency 委托格式需工单确认
  memory_size = var.function_memory_size
  timeout     = 60
  runtime     = "Python3.9"
  handler     = "app.handler"
  code_type       = "zip"
  app         = var.workspace
  description = "HTTP entry point for the durable workflow"
  log_stream_name = "workflow-trigger"
  log_group_id    = huaweicloud_lts_group.functiongraph_logs.id
  enable_lts_log  = true

  # 修复 LTS 依赖顺序问题 - 确保日志流创建完成后再创建函数
  depends_on = [
    huaweicloud_lts_stream.workflow_trigger_log
  ]

  user_data = jsonencode({
    OTEL_SERVICE_NAME           = "workflow-trigger"
    OTEL_EXPORTER_OTLP_ENDPOINT = var.otel_endpoint != "" ? var.otel_endpoint : "https://tracing.${var.hw_region}.myhuaweicloud.com"
    WORKFLOW_REGION            = var.hw_region
    HW_REGION                  = var.hw_region
    HW_PROJECT_ID             = data.huaweicloud_identity_projects.current.id
  })

  tags = merge(var.tags, {
    Component = "workflow-trigger"
  })
}

# ============================================================
# NOTE: huaweicloud_fgs_workflow (状态机) 在 Terraform Provider v1.96.1 中不支持
# 需要在华为云控制台手动创建状态机工作流
# 参考: https://console.huaweicloud.com/functiongraph/
# ============================================================

# ============================================================
# APIG (需要 APIG Instance 才能创建 API，暂跳过)
# APIG 相关资源需要账户余额充足后部署
# ============================================================

# ============================================================
# Outputs
# ============================================================

output "step_functions" {
  description = "Step function details"
  value = {
    extract_text = {
      name = huaweicloud_fgs_function.extract_text.name
      urn  = huaweicloud_fgs_function.extract_text.urn
    }
    summarize = {
      name = huaweicloud_fgs_function.summarize.name
      urn  = huaweicloud_fgs_function.summarize.urn
    }
    human_review = {
      name = huaweicloud_fgs_function.human_review.name
      urn  = huaweicloud_fgs_function.human_review.urn
    }
    publish = {
      name = huaweicloud_fgs_function.publish.name
      urn  = huaweicloud_fgs_function.publish.urn
    }
    workflow_trigger = {
      name = huaweicloud_fgs_function.workflow_trigger.name
      urn  = huaweicloud_fgs_function.workflow_trigger.urn
    }
  }
}

output "obs_bucket" {
  description = "OBS bucket name"
  value       = huaweicloud_obs_bucket.documents.bucket
}

output "lts_log_group" {
  description = "LTS log group name"
  value       = huaweicloud_lts_group.functiongraph_logs.group_name
}

output "region" {
  description = "Huawei Cloud region"
  value       = var.hw_region
}

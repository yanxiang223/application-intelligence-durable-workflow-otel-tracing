# ─────────────────────────────────────────────────────────────────
# variables.tf
# Terraform variables for durable-workflow-sample on Huawei Cloud
# ─────────────────────────────────────────────────────────────────

variable "hw_access_key" {
  description = "Huawei Cloud Access Key ID"
  type        = string
  sensitive   = true
}

variable "hw_secret_key" {
  description = "Huawei Cloud Secret Access Key"
  type        = string
  sensitive   = true
}

variable "hw_region" {
  description = "Huawei Cloud region"
  type        = string
  default     = "cn-north-4"
}

variable "workspace" {
  description = "FunctionGraph workspace (usually 'default')"
  type        = string
  default     = "default"
}

variable "bucket_name" {
  description = "OBS bucket name for document storage (must be globally unique)"
  type        = string
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}

variable "function_timeout" {
  description = "Function execution timeout in seconds (max 900)"
  type        = number
  default     = 60
}

variable "function_memory_size" {
  description = "Function memory size in MB"
  type        = number
  default     = 512
}

variable "otel_endpoint" {
  description = "OpenTelemetry OTLP exporter endpoint (Distributed Tracing Service)"
  type        = string
  default     = "" # Set by provider; leave empty to use cn-north-4 default
}

variable "vpc_id" {
  description = "VPC ID for private function deployment (optional, leave empty for public)"
  type        = string
  default     = ""
}

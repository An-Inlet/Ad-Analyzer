variable "project_id" {
  type    = string
  default = "totemic-alchemy-502420-p4"
}
variable "region" {
  type    = string
  default = "us-west1"
}
variable "environment" {
  type    = string
  default = "production"

  validation {
    condition = (
      can(regex("^[a-z][a-z0-9-]{0,10}[a-z0-9]$", var.environment)) &&
      !contains(["dev", "prod", "stg"], var.environment)
    )
    error_message = "Environment must be 2-12 lowercase letters, digits, or hyphens; start with a letter; end with a letter or digit; and not be a reserved service-account abbreviation (dev, prod, or stg)."
  }
}
variable "gateway_image" {
  type        = string
  description = "Immutable Artifact Registry CRM gateway image reference."

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.gateway_image))
    error_message = "Gateway image must be an immutable image reference ending in @sha256:<64 lowercase hexadecimal characters>."
  }
}
variable "worker_image" {
  type        = string
  description = "Immutable Artifact Registry CRM worker image reference."

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.worker_image))
    error_message = "Worker image must be an immutable image reference ending in @sha256:<64 lowercase hexadecimal characters>."
  }
}
variable "database_password_secret_id" {
  type    = string
  default = "DATABASE_PASSWORD"

  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{1,255}$", var.database_password_secret_id))
    error_message = "Database password secret ID must contain 1-255 letters, digits, hyphens, or underscores."
  }
}
variable "webhook_secret_id" {
  type    = string
  default = "denticode-production-crm-webhook-hmac"

  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{1,255}$", var.webhook_secret_id))
    error_message = "Webhook secret ID must contain 1-255 letters, digits, hyphens, or underscores."
  }
}
variable "cloud_sql_connection_name" {
  type    = string
  default = "totemic-alchemy-502420-p4:us-west1:denticode-analyzer-postgres"
}
variable "database_user" {
  type    = string
  default = "denticode_app"
}
variable "database_name" {
  type    = string
  default = "denticode_ads_optimizer"
}

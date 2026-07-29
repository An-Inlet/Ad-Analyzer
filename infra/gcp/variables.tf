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
}
variable "gateway_image" {
  type        = string
  description = "Immutable Artifact Registry CRM gateway image reference."
}
variable "worker_image" {
  type        = string
  description = "Immutable Artifact Registry CRM worker image reference."
}
variable "database_secret_id" {
  type    = string
  default = "denticode-crm-database-url"
}

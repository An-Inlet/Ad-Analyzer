locals {
  prefix = "ad-analyzer-${var.environment}-crm"
  service_account_environment = lookup({
    development = "dev"
    production  = "prod"
    staging     = "stg"
  }, var.environment, var.environment)
  service_account_prefix = "aa-${local.service_account_environment}-crm"
  service_account_ids = {
    api_gateway = "${local.service_account_prefix}-api-gw"
    gateway     = "${local.service_account_prefix}-gateway"
    pubsub_push = "${local.service_account_prefix}-push"
    worker      = "${local.service_account_prefix}-worker"
  }
  apis = toset([
    "apigateway.googleapis.com", "artifactregistry.googleapis.com", "iam.googleapis.com",
    "pubsub.googleapis.com", "run.googleapis.com", "secretmanager.googleapis.com",
    "servicecontrol.googleapis.com", "servicemanagement.googleapis.com",
    "sqladmin.googleapis.com",
  ])
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_project_service" "required" {
  for_each           = local.apis
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "gateway" {
  account_id   = local.service_account_ids.gateway
  display_name = "CRM gateway (publish only)"
}
resource "google_service_account" "worker" {
  account_id   = local.service_account_ids.worker
  display_name = "CRM worker (database processing only)"
}
resource "google_service_account" "pubsub_push" {
  account_id   = local.service_account_ids.pubsub_push
  display_name = "CRM Pub/Sub push authenticator"
}
resource "google_service_account" "api_gateway" {
  account_id   = local.service_account_ids.api_gateway
  display_name = "API Gateway CRM invoker"
}

resource "google_pubsub_topic" "events" { name = "${local.prefix}-events" }
resource "google_pubsub_topic" "dead_letter" { name = "${local.prefix}-dead-letter" }
resource "google_pubsub_subscription" "worker" {
  name                       = "${local.prefix}-worker"
  topic                      = google_pubsub_topic.events.id
  ack_deadline_seconds       = 60
  message_retention_duration = "604800s"
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }
  push_config {
    push_endpoint = "${google_cloud_run_v2_service.worker.uri}/internal/pubsub/crm-events"
    oidc_token {
      service_account_email = google_service_account.pubsub_push.email
      audience              = google_cloud_run_v2_service.worker.uri
    }
  }
}

data "google_secret_manager_secret" "webhook" {
  secret_id = var.webhook_secret_id
}

data "google_secret_manager_secret" "database_password" {
  secret_id = var.database_password_secret_id
}

resource "google_cloud_run_v2_service" "gateway" {
  name                = "${local.prefix}-gateway"
  location            = var.region
  deletion_protection = true
  ingress             = "INGRESS_TRAFFIC_ALL"
  template {
    service_account = google_service_account.gateway.email
    containers {
      image = var.gateway_image
      ports {
        container_port = 8000
      }
      env {
        name  = "APP_ENV"
        value = var.environment
      }
      env {
        name  = "AD_ANALYZER_CRM_PUBSUB_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "AD_ANALYZER_CRM_PUBSUB_TOPIC_ID"
        value = google_pubsub_topic.events.name
      }
      env {
        name = "AD_ANALYZER_CRM_WEBHOOK_SECRET"
        value_source {
          secret_key_ref {
            secret  = data.google_secret_manager_secret.webhook.secret_id
            version = "latest"
          }
        }
      }
    }
  }
  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_iam_member.gateway_webhook,
  ]
}

resource "google_cloud_run_v2_service" "worker" {
  name                = "${local.prefix}-worker"
  location            = var.region
  deletion_protection = true
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  template {
    service_account = google_service_account.worker.email
    containers {
      image = var.worker_image
      ports {
        container_port = 8000
      }
      env {
        name  = "AD_ANALYZER_CRM_PUSH_OIDC_AUDIENCE"
        value = var.worker_push_oidc_audience
      }
      env {
        name  = "AD_ANALYZER_CRM_PUSH_SERVICE_ACCOUNT_EMAIL"
        value = google_service_account.pubsub_push.email
      }
      env {
        name  = "APP_ENV"
        value = var.environment
      }
      env {
        name  = "CLOUD_SQL_CONNECTION_NAME"
        value = var.cloud_sql_connection_name
      }
      env {
        name  = "DATABASE_USER"
        value = var.database_user
      }
      env {
        name  = "DATABASE_NAME"
        value = var.database_name
      }
      env {
        name = "DATABASE_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = data.google_secret_manager_secret.database_password.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "AD_ANALYZER_REQUIRED_SECRET_NAMES"
        value = "DATABASE_PASSWORD"
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [var.cloud_sql_connection_name]
      }
    }
  }
  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_iam_member.worker_database,
    google_project_iam_member.worker_cloud_sql_client,
  ]
}

resource "google_pubsub_topic_iam_member" "gateway_publish" {
  topic  = google_pubsub_topic.events.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.gateway.email}"
}
resource "google_pubsub_topic_iam_member" "dead_letter_service_agent_publish" {
  topic  = google_pubsub_topic.dead_letter.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}
resource "google_pubsub_subscription_iam_member" "dead_letter_service_agent_forward" {
  subscription = google_pubsub_subscription.worker.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_secret_manager_secret_iam_member" "gateway_webhook" {
  secret_id = data.google_secret_manager_secret.webhook.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.gateway.email}"
}
resource "google_secret_manager_secret_iam_member" "worker_database" {
  secret_id = data.google_secret_manager_secret.database_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.worker.email}"
}
resource "google_project_iam_member" "worker_cloud_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.worker.email}"
}
resource "google_cloud_run_v2_service_iam_member" "api_gateway_invoker" {
  location = google_cloud_run_v2_service.gateway.location
  name     = google_cloud_run_v2_service.gateway.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.api_gateway.email}"
}
resource "google_cloud_run_v2_service_iam_member" "pubsub_push_invoker" {
  location = google_cloud_run_v2_service.worker.location
  name     = google_cloud_run_v2_service.worker.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_push.email}"
}
resource "google_service_account_iam_member" "pubsub_service_agent_push_token" {
  service_account_id = google_service_account.pubsub_push.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_api_gateway_api" "crm" {
  provider = google-beta
  api_id   = "${local.prefix}-api"
}
resource "google_api_gateway_api_config" "crm" {
  provider             = google-beta
  api                  = google_api_gateway_api.crm.api_id
  api_config_id_prefix = "${local.prefix}-config-"
  gateway_config {
    backend_config {
      google_service_account = google_service_account.api_gateway.email
    }
  }
  openapi_documents {
    document {
      path     = "openapi.yaml"
      contents = base64encode(templatefile("${path.module}/openapi.yaml.tftpl", { gateway_url = google_cloud_run_v2_service.gateway.uri }))
    }
  }
  lifecycle {
    create_before_destroy = true
  }
}
resource "google_api_gateway_gateway" "crm" {
  provider   = google-beta
  gateway_id = "${local.prefix}-gateway"
  api_config = google_api_gateway_api_config.crm.id
  region     = var.api_gateway_region
}

check "service_account_ids" {
  assert {
    condition = alltrue([
      for account_id in values(local.service_account_ids) :
      length(account_id) >= 6 && length(account_id) <= 30 && can(regex("^[a-z][a-z0-9-]*[a-z0-9]$", account_id))
    ])
    error_message = "Generated service-account IDs must contain 6-30 lowercase letters, digits, or hyphens, and must start with a letter and end with a letter or digit."
  }
}

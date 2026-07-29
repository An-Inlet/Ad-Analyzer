locals {
  prefix = "denticode-${var.environment}-crm"
  apis = toset([
    "apigateway.googleapis.com", "artifactregistry.googleapis.com", "iam.googleapis.com",
    "pubsub.googleapis.com", "run.googleapis.com", "secretmanager.googleapis.com",
    "servicecontrol.googleapis.com", "servicemanagement.googleapis.com",
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
  account_id   = "${local.prefix}-gateway"
  display_name = "CRM gateway (publish only)"
}
resource "google_service_account" "worker" {
  account_id   = "${local.prefix}-worker"
  display_name = "CRM worker (subscribe only)"
}
resource "google_service_account" "api_gateway" {
  account_id   = "${local.prefix}-api-gw"
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
}

resource "google_secret_manager_secret" "webhook" {
  secret_id = "${local.prefix}-webhook-hmac"
  replication {
    auto {}
  }
}
resource "google_secret_manager_secret" "database" {
  secret_id = var.database_secret_id
  replication {
    auto {}
  }
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
      env {
        name  = "APP_ENV"
        value = var.environment
      }
      env {
        name  = "DENTICODE_CRM_PUBSUB_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "DENTICODE_CRM_PUBSUB_TOPIC_ID"
        value = google_pubsub_topic.events.name
      }
      env {
        name = "DENTICODE_CRM_WEBHOOK_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.webhook.secret_id
            version = "latest"
          }
        }
      }
    }
  }
  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service" "worker" {
  name                = "${local.prefix}-worker"
  location            = var.region
  deletion_protection = true
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  template {
    service_account = google_service_account.worker.email
    containers {
      image   = var.worker_image
      command = ["python", "-m", "app.jobs.crm_worker"]
      env {
        name  = "APP_ENV"
        value = var.environment
      }
      env {
        name  = "DENTICODE_CRM_PUBSUB_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "DENTICODE_CRM_PUBSUB_SUBSCRIPTION_ID"
        value = google_pubsub_subscription.worker.name
      }
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database.secret_id
            version = "latest"
          }
        }
      }
    }
  }
  depends_on = [google_project_service.required]
}

resource "google_pubsub_topic_iam_member" "gateway_publish" {
  topic  = google_pubsub_topic.events.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.gateway.email}"
}
resource "google_pubsub_subscription_iam_member" "worker_subscribe" {
  subscription = google_pubsub_subscription.worker.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.worker.email}"
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
  secret_id = google_secret_manager_secret.webhook.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.gateway.email}"
}
resource "google_secret_manager_secret_iam_member" "worker_database" {
  secret_id = google_secret_manager_secret.database.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.worker.email}"
}
resource "google_cloud_run_v2_service_iam_member" "api_gateway_invoker" {
  location = google_cloud_run_v2_service.gateway.location
  name     = google_cloud_run_v2_service.gateway.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.api_gateway.email}"
}

resource "google_api_gateway_api" "crm" { api_id = "${local.prefix}-api" }
resource "google_api_gateway_api_config" "crm" {
  api           = google_api_gateway_api.crm.api_id
  api_config_id = "${local.prefix}-config"
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
  lifecycle { create_before_destroy = true }
}
resource "google_api_gateway_gateway" "crm" {
  gateway_id = "${local.prefix}-gateway"
  api_config = google_api_gateway_api_config.crm.id
  region     = var.region
}

output "api_gateway_hostname" { value = google_api_gateway_gateway.crm.default_hostname }
output "gateway_service_name" { value = google_cloud_run_v2_service.gateway.name }
output "worker_service_name" { value = google_cloud_run_v2_service.worker.name }
output "events_topic" { value = google_pubsub_topic.events.name }
output "worker_subscription" { value = google_pubsub_subscription.worker.name }
output "dead_letter_topic" { value = google_pubsub_topic.dead_letter.name }
output "webhook_secret_id" { value = google_secret_manager_secret.webhook.secret_id }
output "service_accounts" { value = { gateway = google_service_account.gateway.email, worker = google_service_account.worker.email, pubsub_push = google_service_account.pubsub_push.email, api_gateway = google_service_account.api_gateway.email } }

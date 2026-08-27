output "instance_public_ip" {
  description = "Public IP of the app instance. API: http://<this>:8000, UI: http://<this>:8501."
  value       = aws_instance.app.public_ip
}

output "ecr_repository_urls" {
  description = "Push target for each service's image, e.g. `docker push <api_url>:latest`."
  value       = { for name, repo in aws_ecr_repository.service : name => repo.repository_url }
}

output "s3_bucket_name" {
  description = "S3 bucket backing StoragePort's S3Storage in prod."
  value       = aws_s3_bucket.storage.bucket
}

output "db_credentials_secret_arn" {
  description = "Secrets Manager ARN holding the generated Postgres password."
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "app_secrets_secret_arn" {
  description = "Secrets Manager ARN to `put-secret-value` the real GEMINI_API_KEY/JWT_SECRET_KEY/JIRA_* into after apply."
  value       = aws_secretsmanager_secret.app_secrets.arn
}

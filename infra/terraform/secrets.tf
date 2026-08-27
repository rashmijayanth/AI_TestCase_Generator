# Two secrets, split by who owns the value:
#  - db_credentials: Terraform generates and owns the Postgres password (a
#    random_password resource), since nothing outside this config needs to
#    supply it.
#  - app_secrets: third-party credentials (Gemini API key, JWT signing
#    secret, Jira token) that Terraform has no business generating or
#    knowing. It provisions the secret *container* with placeholder values;
#    the real values are set out-of-band (`aws secretsmanager put-secret-value`)
#    after apply. ignore_changes on secret_string keeps a later `terraform
#    apply` from stomping on that out-of-band update.

resource "random_password" "db" {
  length  = 32
  special = false # simplifies embedding directly in a libpq connection string
}

resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "${var.project_name}/db-credentials"
  description = "Postgres credentials for the ${var.project_name} EC2 instance."
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db.result
    dbname   = var.db_name
  })
}

resource "aws_secretsmanager_secret" "app_secrets" {
  name        = "${var.project_name}/app-secrets"
  description = "GEMINI_API_KEY / JWT_SECRET_KEY / JIRA_* -- placeholders, filled in out-of-band after apply."
}

resource "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    GEMINI_API_KEY   = "REPLACE_ME"
    JWT_SECRET_KEY   = "REPLACE_ME"
    JIRA_API_TOKEN   = "REPLACE_ME"
    JIRA_EMAIL       = "REPLACE_ME"
    JIRA_BASE_URL    = "REPLACE_ME"
    JIRA_PROJECT_KEY = "REPLACE_ME"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

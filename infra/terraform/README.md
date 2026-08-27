# Terraform (Phase 9)

VPC/EC2/S3/ECR/Secrets Manager/IAM per DESIGN.md §7 — written to a real
standard, `terraform validate`'d locally, but never `terraform apply`'d (no
AWS account required for local development or demo, DESIGN.md §8).

## Layout

| File | What |
|---|---|
| `versions.tf` | Terraform/provider version constraints, AWS provider config |
| `variables.tf` | Inputs — everything has a sane default except `ssh_ingress_cidr`/`ssh_key_name` |
| `vpc.tf` | VPC, 2 public subnets across 2 AZs, IGW, route table — deliberately no NAT/private subnets, nothing here needs private-only placement |
| `security_groups.tf` | SSH (restricted to `var.ssh_ingress_cidr`) + API (8000) + UI (8501) |
| `iam.tf` | EC2 instance role, scoped to exactly this config's ECR repos / Secrets / S3 bucket — no managed AWS-wide policies |
| `ecr.tf` | One repo per `infra/docker/*.Dockerfile` (api, worker, ui) |
| `s3.tf` | Storage bucket for `StoragePort`'s `S3Storage` (prod), versioned + encrypted + fully public-access-blocked |
| `secrets.tf` | `db-credentials` (Terraform-generated password) and `app-secrets` (Gemini/JWT/Jira — placeholder container; real values set out-of-band, `ignore_changes` keeps `apply` from clobbering them) |
| `ec2.tf` | The single EC2 instance (`DESIGN.md §7: EC2 not EKS`) running the whole docker-compose stack |
| `user_data.sh.tftpl` | Instance boot script: installs Docker, pulls the 3 ECR images via `infra/docker/docker-compose.prod.yml`, fetches secrets into `.env` |
| `outputs.tf` | Public IP, ECR repo URLs, S3 bucket name, secret ARNs |
| `terraform.tfvars.example` | Copy to `terraform.tfvars` (gitignored) and fill in `ssh_ingress_cidr`/`ssh_key_name` |

## Verified locally (no AWS account needed)

```bash
terraform fmt -recursive
terraform init -backend=false
terraform validate
```

All three pass clean. `terraform plan`/`apply` need real AWS credentials and
are out of scope here (DESIGN.md §8) — a `terraform plan` is the natural next
step once real credentials are available, before ever running `apply`.

variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short name used as a prefix for every resource this config creates."
  type        = string
  default     = "testgen-ai"
}

variable "environment" {
  description = "Deployment environment tag (this is a portfolio build -- realistically always 'demo')."
  type        = string
  default     = "demo"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for the public subnets, one per AZ in availability_zone_suffixes."
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "availability_zone_suffixes" {
  description = "AZ suffixes (appended to aws_region) for the public subnets."
  type        = list(string)
  default     = ["a", "b"]
}

variable "instance_type" {
  description = "EC2 instance type running docker-compose (api+worker+ui containers, DESIGN.md §7: EC2 not EKS)."
  type        = string
  default     = "t3.medium"
}

variable "root_volume_size_gb" {
  description = "Root EBS volume size in GB -- sized for 3 container images (~3GB combined) plus the base OS and Docker's own layer cache."
  type        = number
  default     = 30
}

variable "ssh_ingress_cidr" {
  description = "CIDR allowed to SSH into the instance. No sane default -- must be set explicitly (e.g. your own IP/32), never left open to 0.0.0.0/0."
  type        = string
}

variable "ssh_key_name" {
  description = "Name of an existing EC2 key pair to associate with the instance, for SSH access."
  type        = string
}

variable "app_ingress_cidr" {
  description = "CIDR allowed to reach the API (8000) and UI (8501) ports directly. Defaults to open, since this is a demo instance behind no load balancer -- tighten for anything longer-lived."
  type        = string
  default     = "0.0.0.0/0"
}

variable "db_name" {
  description = "Postgres database name (matches docker-compose.yml's POSTGRES_DB default)."
  type        = string
  default     = "testgen"
}

variable "db_username" {
  description = "Postgres username (matches docker-compose.yml's POSTGRES_USER default)."
  type        = string
  default     = "testgen"
}

variable "repo_url" {
  description = "Git URL user_data.sh.tftpl clones on first boot to get docker-compose.yml + infra/docker/docker-compose.prod.yml."
  type        = string
  default     = "https://github.com/rashmijayanth/AI_TestCase_Generator.git"
}

resource "aws_security_group" "app" {
  name        = "${var.project_name}-app"
  description = "SSH + the API/UI ports docker-compose exposes on the instance."
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_ingress_cidr]
  }

  ingress {
    description = "FastAPI (docker-compose.yml: api service, port 8000)"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.app_ingress_cidr]
  }

  ingress {
    description = "Streamlit UI (docker-compose.yml: ui service, port 8501)"
    from_port   = 8501
    to_port     = 8501
    protocol    = "tcp"
    cidr_blocks = [var.app_ingress_cidr]
  }

  egress {
    description = "All outbound (image pulls from ECR, Gemini/Jira API calls, package installs)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-app-sg"
  }
}

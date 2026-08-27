data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = var.ssh_key_name

  root_block_device {
    volume_size = var.root_volume_size_gb
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    aws_region                = var.aws_region
    project_name              = var.project_name
    ecr_registry              = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
    repo_url                  = var.repo_url
    db_credentials_secret_arn = aws_secretsmanager_secret.db_credentials.arn
    app_secrets_secret_arn    = aws_secretsmanager_secret.app_secrets.arn
    s3_bucket_name            = aws_s3_bucket.storage.bucket
  })

  tags = {
    Name = "${var.project_name}-app"
  }
}

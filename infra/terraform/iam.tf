# EC2 instance role: pull the 3 ECR images, read the 2 Secrets Manager
# secrets, read/write the S3 storage bucket. Scoped to exactly these
# resources, not managed AWS-wide policies, so the instance can't reach
# anything else in the account.

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  name               = "${var.project_name}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2.name
}

data "aws_iam_policy_document" "ec2_permissions" {
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # GetAuthorizationToken doesn't support resource-level scoping
  }

  statement {
    sid = "EcrPull"
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchCheckLayerAvailability",
    ]
    resources = [for repo in aws_ecr_repository.service : repo.arn]
  }

  statement {
    sid       = "ReadSecrets"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.db_credentials.arn, aws_secretsmanager_secret.app_secrets.arn]
  }

  statement {
    sid = "StorageBucketReadWrite"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [aws_s3_bucket.storage.arn, "${aws_s3_bucket.storage.arn}/*"]
  }
}

resource "aws_iam_role_policy" "ec2" {
  name   = "${var.project_name}-ec2-policy"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.ec2_permissions.json
}

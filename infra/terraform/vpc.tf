# Two public subnets across two AZs (a realistic small-footprint network
# shape), even though only one EC2 instance (ec2.tf) uses one of them --
# deliberately no NAT gateway / private subnets, since nothing here needs
# private-only placement (DESIGN.md §7: "EC2 not EKS... far less infra to
# build/operate" -- a single public instance running docker-compose is the
# whole compute footprint).

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

resource "aws_subnet" "public" {
  count = length(var.public_subnet_cidrs)

  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = "${var.aws_region}${var.availability_zone_suffixes[count.index]}"
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-${var.availability_zone_suffixes[count.index]}"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  count = length(aws_subnet.public)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

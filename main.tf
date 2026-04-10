# =============================================================================
# BITE.co Cloud Cost Management Platform
# Terraform deployment for AWS Academy
#
# Architecture reference: architecture.md §3 Deployment Architecture
# Experiments:
#   - ASR16 (Latencia)    → ALB → manejador_usuarios → POST /projects
#   - ASR17 (Escalabilidad) → ALB → manejador_reportes → POST /events/batch
#                              → RabbitMQ → Worker Pool (Celery)
#
# Instance sizing: t3.micro / t3.small (cheapest viable for AWS Academy)
# =============================================================================

# -----------------------------------------------------------------------------
# VARIABLES — fill before applying
# -----------------------------------------------------------------------------

variable "region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "project_prefix" {
  description = "Prefix used for naming all AWS resources"
  type        = string
  default     = "bite"
}

variable "key_name" {
  description = "EC2 key pair name for SSH access (must exist in your AWS Academy account)"
  type        = string
}

variable "allowed_ssh_cidr" {
  description = "CIDR allowed for SSH access. Restrict to your IP in production."
  type        = string
  default     = "0.0.0.0/0"
}

variable "repository" {
  description = "Git repository URL (HTTPS) containing the Django microservices"
  type        = string
  default     = "https://github.com/dcantorni/Arquisoft-sprint2-Leopartech"
}

variable "branch" {
  description = "Git branch to deploy"
  type        = string
  default     = "main"
}

variable "celery_worker_concurrency" {
  description = "Number of concurrent Celery worker processes per worker instance (ASR17)"
  type        = number
  default     = 4
}

# Instance types — kept at the smallest viable size for AWS Academy budget
variable "instance_type_app" {
  description = "EC2 type for Django app servers (manejador_usuarios, manejador_cloud, manejador_reportes)"
  type        = string
  default     = "t3.small"
}

variable "instance_type_db" {
  description = "EC2 type for PostgreSQL servers (one per microservice)"
  type        = string
  default     = "t3.micro"
}

variable "instance_type_support" {
  description = "EC2 type for shared infrastructure: Redis and RabbitMQ"
  type        = string
  default     = "t3.micro"
}

variable "instance_type_worker" {
  description = "EC2 type for Celery worker pool instances (ASR17 scalability)"
  type        = string
  default     = "t3.small"
}

# -----------------------------------------------------------------------------
# PROVIDER & DATA SOURCES
# -----------------------------------------------------------------------------

provider "aws" {
  region = var.region
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Ubuntu 22.04 LTS — matches architecture.md deployment spec
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# -----------------------------------------------------------------------------
# LOCALS
# -----------------------------------------------------------------------------

locals {
  project_name = "${var.project_prefix}-cloud-cost-platform"
  repo_dir     = "/opt/biteco"

  common_tags = {
    Project   = local.project_name
    ManagedBy = "Terraform"
  }

  # Shared startup script: clones the repo and waits for dependencies
  # Usage: interpolate after setting env vars in each user_data block
  git_bootstrap = <<-SCRIPT
    sudo apt-get update -y
    sudo apt-get install -y python3-pip git build-essential libpq-dev python3-dev postgresql-client netcat-openbsd
    if [ ! -d "${local.repo_dir}/.git" ]; then
      sudo git clone ${var.repository} ${local.repo_dir}
    fi
    cd ${local.repo_dir}
    git fetch origin ${var.branch} || true
    git checkout ${var.branch} || true
    git pull origin ${var.branch} || true
    sudo python3 -m pip install --upgrade pip
  SCRIPT
}

# -----------------------------------------------------------------------------
# SECURITY GROUPS
# architecture.md §3 — each tier has its own SG with minimal ingress rules
# -----------------------------------------------------------------------------

resource "aws_security_group" "ssh" {
  name        = "${var.project_prefix}-ssh"
  description = "SSH access for all instances"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-ssh" })
}

# ALB security group — accepts HTTP from anywhere, forwards to app servers
resource "aws_security_group" "alb" {
  name        = "${var.project_prefix}-alb"
  description = "Application Load Balancer — public HTTP ingress"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP from Internet (JMeter targets this)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-alb" })
}

# App servers — only accept traffic from the ALB and SSH
resource "aws_security_group" "app" {
  name        = "${var.project_prefix}-app"
  description = "Django app servers — accepts from ALB only"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "manejador_usuarios from ALB"
    from_port       = 8001
    to_port         = 8001
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description = "manejador_cloud — internal VPC only (no ALB)"
    from_port   = 8002
    to_port     = 8002
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }

  ingress {
    description     = "manejador_reportes from ALB"
    from_port       = 8003
    to_port         = 8003
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-app" })
}

# Databases — only reachable from within the VPC
resource "aws_security_group" "db" {
  name        = "${var.project_prefix}-db"
  description = "PostgreSQL — VPC-internal only"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "PostgreSQL from VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-db" })
}

# Redis — VPC-internal only
resource "aws_security_group" "cache" {
  name        = "${var.project_prefix}-cache"
  description = "Redis — VPC-internal only"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "Redis from VPC"
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-cache" })
}

# RabbitMQ — VPC-internal AMQP + management UI
resource "aws_security_group" "broker" {
  name        = "${var.project_prefix}-broker"
  description = "RabbitMQ — VPC-internal AMQP and management UI"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "AMQP from VPC"
    from_port   = 5672
    to_port     = 5672
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }

  ingress {
    description = "RabbitMQ Management UI from VPC"
    from_port   = 15672
    to_port     = 15672
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-broker" })
}

# Worker pool — no inbound HTTP needed, only SSH and VPC egress
resource "aws_security_group" "worker" {
  name        = "${var.project_prefix}-worker"
  description = "Celery worker pool — SSH only, full VPC egress"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-worker" })
}

# -----------------------------------------------------------------------------
# SHARED INFRASTRUCTURE
# architecture.md §3.5 — Redis (Elasticache) + RabbitMQ (AMQP)
# Using EC2 for AWS Academy compatibility (Elasticache requires VPC config)
# -----------------------------------------------------------------------------

resource "aws_instance" "redis" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type_support
  subnet_id                   = element(tolist(data.aws_subnets.default.ids), 0)
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.cache.id, aws_security_group.ssh.id]
  key_name                    = var.key_name

  root_block_device {
    volume_size = 10
    volume_type = "gp3"
  }

  user_data = <<-EOT
    #!/bin/bash
    set -euxo pipefail
    export DEBIAN_FRONTEND=noninteractive
    sudo apt-get update -y
    sudo apt-get install -y redis-server
    # Allow connections from entire VPC
    sudo sed -i 's/^bind 127.0.0.1/bind 0.0.0.0/' /etc/redis/redis.conf
    sudo sed -i 's/^protected-mode yes/protected-mode no/' /etc/redis/redis.conf
    # LRU eviction policy — matches docker-compose config
    echo "maxmemory 256mb" | sudo tee -a /etc/redis/redis.conf
    echo "maxmemory-policy allkeys-lru" | sudo tee -a /etc/redis/redis.conf
    sudo systemctl enable redis-server
    sudo systemctl restart redis-server
  EOT

  tags = merge(local.common_tags, {
    Name    = "${var.project_prefix}-redis"
    Role    = "cache"
    Service = "redis"
  })
}

resource "aws_instance" "rabbitmq" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type_support
  subnet_id                   = element(tolist(data.aws_subnets.default.ids), 0)
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.broker.id, aws_security_group.ssh.id]
  key_name                    = var.key_name

  root_block_device {
    volume_size = 10
    volume_type = "gp3"
  }

  user_data = <<-EOT
    #!/bin/bash
    set -euxo pipefail
    export DEBIAN_FRONTEND=noninteractive
    sudo apt-get update -y
    sudo apt-get install -y rabbitmq-server
    sudo systemctl enable rabbitmq-server
    sudo systemctl start rabbitmq-server
    # Enable management UI
    sudo rabbitmq-plugins enable rabbitmq_management
    # Create vhost and user matching docker-compose credentials
    sudo rabbitmqctl add_vhost bite_vhost || true
    sudo rabbitmqctl add_user bite bite_pass || true
    sudo rabbitmqctl set_user_tags bite administrator || true
    sudo rabbitmqctl set_permissions -p bite_vhost bite ".*" ".*" ".*" || true
    sudo systemctl restart rabbitmq-server
  EOT

  tags = merge(local.common_tags, {
    Name    = "${var.project_prefix}-rabbitmq"
    Role    = "broker"
    Service = "rabbitmq"
  })
}

# -----------------------------------------------------------------------------
# DATABASES — one PostgreSQL EC2 per microservice
# architecture.md §3.4 — database isolation per service
# -----------------------------------------------------------------------------

resource "aws_instance" "postgres_usuarios" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type_db
  subnet_id                   = element(tolist(data.aws_subnets.default.ids), 0)
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.db.id, aws_security_group.ssh.id]
  key_name                    = var.key_name

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  user_data = <<-EOT
    #!/bin/bash
    set -euxo pipefail
    export DEBIAN_FRONTEND=noninteractive
    sudo apt-get update -y
    sudo apt-get install -y postgresql postgresql-contrib
    PG_VERSION=$(ls /etc/postgresql | sort -V | tail -n 1)
    DB_CONF=/etc/postgresql/$PG_VERSION/main
    echo "listen_addresses = '*'" | sudo tee -a $DB_CONF/postgresql.conf
    grep -q "${data.aws_vpc.default.cidr_block}" $DB_CONF/pg_hba.conf || \
      echo "host all all ${data.aws_vpc.default.cidr_block} scram-sha-256" | sudo tee -a $DB_CONF/pg_hba.conf
    sudo systemctl enable postgresql
    sudo systemctl restart postgresql
    sleep 5
    sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='admin'" | grep -q 1 || \
      sudo -u postgres psql -c "CREATE ROLE admin LOGIN PASSWORD 'admin123';"
    sudo -u postgres createdb -O admin usuarios_db || true
  EOT

  tags = merge(local.common_tags, {
    Name    = "${var.project_prefix}-postgres-usuarios"
    Role    = "database"
    Service = "usuarios"
  })
}

resource "aws_instance" "postgres_cloud" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type_db
  subnet_id                   = element(tolist(data.aws_subnets.default.ids), 0)
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.db.id, aws_security_group.ssh.id]
  key_name                    = var.key_name

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  user_data = <<-EOT
    #!/bin/bash
    set -euxo pipefail
    export DEBIAN_FRONTEND=noninteractive
    sudo apt-get update -y
    sudo apt-get install -y postgresql postgresql-contrib
    PG_VERSION=$(ls /etc/postgresql | sort -V | tail -n 1)
    DB_CONF=/etc/postgresql/$PG_VERSION/main
    echo "listen_addresses = '*'" | sudo tee -a $DB_CONF/postgresql.conf
    grep -q "${data.aws_vpc.default.cidr_block}" $DB_CONF/pg_hba.conf || \
      echo "host all all ${data.aws_vpc.default.cidr_block} scram-sha-256" | sudo tee -a $DB_CONF/pg_hba.conf
    sudo systemctl enable postgresql
    sudo systemctl restart postgresql
    sleep 5
    sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='admin'" | grep -q 1 || \
      sudo -u postgres psql -c "CREATE ROLE admin LOGIN PASSWORD 'admin123';"
    sudo -u postgres createdb -O admin cloud_db || true
  EOT

  tags = merge(local.common_tags, {
    Name    = "${var.project_prefix}-postgres-cloud"
    Role    = "database"
    Service = "cloud"
  })
}

resource "aws_instance" "postgres_reportes" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type_db
  subnet_id                   = element(tolist(data.aws_subnets.default.ids), 0)
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.db.id, aws_security_group.ssh.id]
  key_name                    = var.key_name

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  user_data = <<-EOT
    #!/bin/bash
    set -euxo pipefail
    export DEBIAN_FRONTEND=noninteractive
    sudo apt-get update -y
    sudo apt-get install -y postgresql postgresql-contrib
    PG_VERSION=$(ls /etc/postgresql | sort -V | tail -n 1)
    DB_CONF=/etc/postgresql/$PG_VERSION/main
    echo "listen_addresses = '*'" | sudo tee -a $DB_CONF/postgresql.conf
    grep -q "${data.aws_vpc.default.cidr_block}" $DB_CONF/pg_hba.conf || \
      echo "host all all ${data.aws_vpc.default.cidr_block} scram-sha-256" | sudo tee -a $DB_CONF/pg_hba.conf
    sudo systemctl enable postgresql
    sudo systemctl restart postgresql
    sleep 5
    sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='admin'" | grep -q 1 || \
      sudo -u postgres psql -c "CREATE ROLE admin LOGIN PASSWORD 'admin123';"
    sudo -u postgres createdb -O admin reportes_db || true
  EOT

  tags = merge(local.common_tags, {
    Name    = "${var.project_prefix}-postgres-reportes"
    Role    = "database"
    Service = "reportes"
  })
}

# -----------------------------------------------------------------------------
# APPLICATION SERVERS
# architecture.md §3.3 — Django services on Ubuntu 22.04
# -----------------------------------------------------------------------------

resource "aws_instance" "manejador_usuarios" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type_app
  subnet_id                   = element(tolist(data.aws_subnets.default.ids), 0)
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.app.id, aws_security_group.ssh.id]
  key_name                    = var.key_name

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  # Depends on all infra — user_data waits with nc before starting the service
  depends_on = [
    aws_instance.postgres_usuarios,
    aws_instance.redis,
    aws_instance.rabbitmq,
    aws_instance.manejador_cloud,
  ]

  user_data = <<-EOT
    #!/bin/bash
    set -euxo pipefail
    export DEBIAN_FRONTEND=noninteractive

    # Environment — mirrors docker-compose env vars exactly
    sudo tee /etc/environment <<ENV
    DATABASE_HOST=${aws_instance.postgres_usuarios.private_ip}
    DATABASE_PORT=5432
    DATABASE_NAME=usuarios_db
    DATABASE_USER=admin
    DATABASE_PASSWORD=admin123
    REDIS_URL=redis://${aws_instance.redis.private_ip}:6379/0
    RABBITMQ_URL=amqp://bite:bite_pass@${aws_instance.rabbitmq.private_ip}:5672/bite_vhost
    RESOURCE_SERVICE_URL=http://${aws_instance.manejador_cloud.private_ip}:8002
    ALLOWED_HOSTS=*
    DEBUG=True
    SECRET_KEY=bite-terraform-secret-key
    EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
    ENV

    export DATABASE_HOST=${aws_instance.postgres_usuarios.private_ip}
    export DATABASE_PORT=5432
    export DATABASE_NAME=usuarios_db
    export DATABASE_USER=admin
    export DATABASE_PASSWORD=admin123
    export REDIS_URL=redis://${aws_instance.redis.private_ip}:6379/0
    export RABBITMQ_URL=amqp://bite:bite_pass@${aws_instance.rabbitmq.private_ip}:5672/bite_vhost
    export RESOURCE_SERVICE_URL=http://${aws_instance.manejador_cloud.private_ip}:8002
    export ALLOWED_HOSTS=*
    export DEBUG=True
    export SECRET_KEY=bite-terraform-secret-key

    ${local.git_bootstrap}

    # Wait for dependencies
    until nc -z ${aws_instance.postgres_usuarios.private_ip} 5432; do sleep 5; done
    until nc -z ${aws_instance.redis.private_ip} 6379; do sleep 5; done
    until nc -z ${aws_instance.rabbitmq.private_ip} 5672; do sleep 5; done
    until nc -z ${aws_instance.manejador_cloud.private_ip} 8002; do sleep 5; done

    cd ${local.repo_dir}/manejador_usuarios
    sudo python3 -m pip install -r requirements.txt
    python3 manage.py migrate --noinput || true
    nohup python3 manage.py runserver 0.0.0.0:8001 > /var/log/manejador_usuarios.log 2>&1 &
  EOT

  tags = merge(local.common_tags, {
    Name    = "${var.project_prefix}-manejador-usuarios"
    Role    = "app-server"
    Service = "usuarios"
  })
}

resource "aws_instance" "manejador_cloud" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type_app
  subnet_id                   = element(tolist(data.aws_subnets.default.ids), 0)
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.app.id, aws_security_group.ssh.id]
  key_name                    = var.key_name

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  depends_on = [
    aws_instance.postgres_cloud,
    aws_instance.redis,
  ]

  user_data = <<-EOT
    #!/bin/bash
    set -euxo pipefail
    export DEBIAN_FRONTEND=noninteractive

    sudo tee /etc/environment <<ENV
    DATABASE_HOST=${aws_instance.postgres_cloud.private_ip}
    DATABASE_PORT=5432
    DATABASE_NAME=cloud_db
    DATABASE_USER=admin
    DATABASE_PASSWORD=admin123
    REDIS_URL=redis://${aws_instance.redis.private_ip}:6379/1
    ALLOWED_HOSTS=*
    DEBUG=True
    SECRET_KEY=bite-terraform-secret-key
    ENV

    export DATABASE_HOST=${aws_instance.postgres_cloud.private_ip}
    export DATABASE_PORT=5432
    export DATABASE_NAME=cloud_db
    export DATABASE_USER=admin
    export DATABASE_PASSWORD=admin123
    export REDIS_URL=redis://${aws_instance.redis.private_ip}:6379/1
    export ALLOWED_HOSTS=*
    export DEBUG=True
    export SECRET_KEY=bite-terraform-secret-key

    ${local.git_bootstrap}

    until nc -z ${aws_instance.postgres_cloud.private_ip} 5432; do sleep 5; done
    until nc -z ${aws_instance.redis.private_ip} 6379; do sleep 5; done

    cd ${local.repo_dir}/manejador_cloud
    sudo python3 -m pip install -r requirements.txt
    python3 manage.py migrate --noinput || true
    # Seed ProveedorCloud, CuentaCloud, RecursoCloud, MetricaConsumo
    python3 manage.py seed_cloud_data || true
    nohup python3 manage.py runserver 0.0.0.0:8002 > /var/log/manejador_cloud.log 2>&1 &
  EOT

  tags = merge(local.common_tags, {
    Name    = "${var.project_prefix}-manejador-cloud"
    Role    = "app-server"
    Service = "cloud"
  })
}

resource "aws_instance" "manejador_reportes" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type_app
  subnet_id                   = element(tolist(data.aws_subnets.default.ids), 0)
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.app.id, aws_security_group.ssh.id]
  key_name                    = var.key_name

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  depends_on = [
    aws_instance.postgres_reportes,
    aws_instance.redis,
    aws_instance.rabbitmq,
  ]

  user_data = <<-EOT
    #!/bin/bash
    set -euxo pipefail
    export DEBIAN_FRONTEND=noninteractive

    sudo tee /etc/environment <<ENV
    DATABASE_HOST=${aws_instance.postgres_reportes.private_ip}
    DATABASE_PORT=5432
    DATABASE_NAME=reportes_db
    DATABASE_USER=admin
    DATABASE_PASSWORD=admin123
    REDIS_URL=redis://${aws_instance.redis.private_ip}:6379/2
    CELERY_RESULT_BACKEND=redis://${aws_instance.redis.private_ip}:6379/3
    RABBITMQ_URL=amqp://bite:bite_pass@${aws_instance.rabbitmq.private_ip}:5672/bite_vhost
    CELERY_BROKER_URL=amqp://bite:bite_pass@${aws_instance.rabbitmq.private_ip}:5672/bite_vhost
    ALLOWED_HOSTS=*
    DEBUG=True
    SECRET_KEY=bite-terraform-secret-key
    EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
    ENV

    export DATABASE_HOST=${aws_instance.postgres_reportes.private_ip}
    export DATABASE_PORT=5432
    export DATABASE_NAME=reportes_db
    export DATABASE_USER=admin
    export DATABASE_PASSWORD=admin123
    export REDIS_URL=redis://${aws_instance.redis.private_ip}:6379/2
    export CELERY_RESULT_BACKEND=redis://${aws_instance.redis.private_ip}:6379/3
    export RABBITMQ_URL=amqp://bite:bite_pass@${aws_instance.rabbitmq.private_ip}:5672/bite_vhost
    export CELERY_BROKER_URL=amqp://bite:bite_pass@${aws_instance.rabbitmq.private_ip}:5672/bite_vhost
    export ALLOWED_HOSTS=*
    export DEBUG=True
    export SECRET_KEY=bite-terraform-secret-key

    ${local.git_bootstrap}

    until nc -z ${aws_instance.postgres_reportes.private_ip} 5432; do sleep 5; done
    until nc -z ${aws_instance.redis.private_ip} 6379; do sleep 5; done
    until nc -z ${aws_instance.rabbitmq.private_ip} 5672; do sleep 5; done

    cd ${local.repo_dir}/manejador_reportes
    sudo python3 -m pip install -r requirements.txt
    python3 manage.py migrate --noinput || true
    nohup python3 manage.py runserver 0.0.0.0:8003 > /var/log/manejador_reportes.log 2>&1 &
  EOT

  tags = merge(local.common_tags, {
    Name    = "${var.project_prefix}-manejador-reportes"
    Role    = "app-server"
    Service = "reportes"
  })
}

# -----------------------------------------------------------------------------
# CELERY WORKER POOL
# architecture.md §4.1 — Worker Pool (Auto-scaling) for ASR17
# Two EC2 instances running Celery workers, each with configurable concurrency
# -----------------------------------------------------------------------------

resource "aws_instance" "worker_pool" {
  for_each = toset(["a", "b"])

  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type_worker
  subnet_id                   = element(tolist(data.aws_subnets.default.ids), 0)
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.worker.id, aws_security_group.ssh.id]
  key_name                    = var.key_name

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  depends_on = [
    aws_instance.postgres_reportes,
    aws_instance.redis,
    aws_instance.rabbitmq,
  ]

  user_data = <<-EOT
    #!/bin/bash
    set -euxo pipefail
    export DEBIAN_FRONTEND=noninteractive

    sudo tee /etc/environment <<ENV
    DATABASE_HOST=${aws_instance.postgres_reportes.private_ip}
    DATABASE_PORT=5432
    DATABASE_NAME=reportes_db
    DATABASE_USER=admin
    DATABASE_PASSWORD=admin123
    REDIS_URL=redis://${aws_instance.redis.private_ip}:6379/2
    CELERY_RESULT_BACKEND=redis://${aws_instance.redis.private_ip}:6379/3
    RABBITMQ_URL=amqp://bite:bite_pass@${aws_instance.rabbitmq.private_ip}:5672/bite_vhost
    CELERY_BROKER_URL=amqp://bite:bite_pass@${aws_instance.rabbitmq.private_ip}:5672/bite_vhost
    CELERY_WORKER_CONCURRENCY=${var.celery_worker_concurrency}
    DEBUG=True
    SECRET_KEY=bite-terraform-secret-key
    ENV

    export DATABASE_HOST=${aws_instance.postgres_reportes.private_ip}
    export DATABASE_PORT=5432
    export DATABASE_NAME=reportes_db
    export DATABASE_USER=admin
    export DATABASE_PASSWORD=admin123
    export REDIS_URL=redis://${aws_instance.redis.private_ip}:6379/2
    export CELERY_RESULT_BACKEND=redis://${aws_instance.redis.private_ip}:6379/3
    export RABBITMQ_URL=amqp://bite:bite_pass@${aws_instance.rabbitmq.private_ip}:5672/bite_vhost
    export CELERY_BROKER_URL=amqp://bite:bite_pass@${aws_instance.rabbitmq.private_ip}:5672/bite_vhost
    export CELERY_WORKER_CONCURRENCY=${var.celery_worker_concurrency}
    export DEBUG=True
    export SECRET_KEY=bite-terraform-secret-key

    ${local.git_bootstrap}

    until nc -z ${aws_instance.postgres_reportes.private_ip} 5432; do sleep 5; done
    until nc -z ${aws_instance.redis.private_ip} 6379; do sleep 5; done
    until nc -z ${aws_instance.rabbitmq.private_ip} 5672; do sleep 5; done

    cd ${local.repo_dir}/manejador_reportes
    sudo python3 -m pip install -r requirements.txt
    # Celery reads directly from RabbitMQ — no pika consumer middleman
    nohup python3 -m celery -A manejador_reportes.celery worker \
      --loglevel=info \
      --concurrency=${var.celery_worker_concurrency} \
      > /var/log/bite-worker-${each.key}.log 2>&1 &
  EOT

  tags = merge(local.common_tags, {
    Name = "${var.project_prefix}-worker-${each.key}"
    Role = "worker"
  })
}

# -----------------------------------------------------------------------------
# APPLICATION LOAD BALANCER
# architecture.md §3.2 — AWS Application Load Balancer
# Routes ASR16 traffic → manejador_usuarios (port 8001)
# Routes ASR17 traffic → manejador_reportes (port 8003)
# manejador_cloud is internal only — not exposed via ALB
# -----------------------------------------------------------------------------

resource "aws_lb" "main" {
  name               = "${var.project_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = tolist(data.aws_subnets.default.ids)

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-alb" })
}

# Target group for manejador_usuarios — ASR16 latency experiment
resource "aws_lb_target_group" "usuarios" {
  name     = "${var.project_prefix}-tg-usuarios"
  port     = 8001
  protocol = "HTTP"
  vpc_id   = data.aws_vpc.default.id

  health_check {
    path                = "/health"
    interval            = 30
    timeout             = 10
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-tg-usuarios" })
}

# Target group for manejador_reportes — ASR17 scalability experiment
resource "aws_lb_target_group" "reportes" {
  name     = "${var.project_prefix}-tg-reportes"
  port     = 8003
  protocol = "HTTP"
  vpc_id   = data.aws_vpc.default.id

  health_check {
    path                = "/health"
    interval            = 30
    timeout             = 10
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-tg-reportes" })
}

# Register app server instances with their target groups
resource "aws_lb_target_group_attachment" "usuarios" {
  target_group_arn = aws_lb_target_group.usuarios.arn
  target_id        = aws_instance.manejador_usuarios.id
  port             = 8001
}

resource "aws_lb_target_group_attachment" "reportes" {
  target_group_arn = aws_lb_target_group.reportes.arn
  target_id        = aws_instance.manejador_reportes.id
  port             = 8003
}

# ALB Listener — routes by path prefix
# /projects* → manejador_usuarios (ASR16)
# /events*   → manejador_reportes (ASR17)
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  # Default action routes to usuarios (ASR16 is the primary latency test)
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.usuarios.arn
  }
}

resource "aws_lb_listener_rule" "events" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.reportes.arn
  }

  condition {
    path_pattern {
      values = ["/events/*", "/events"]
    }
  }
}

# -----------------------------------------------------------------------------
# OUTPUTS — use these in JMeter HTTP Request samplers
# -----------------------------------------------------------------------------

output "alb_dns_name" {
  description = "ALB DNS name — use this as the JMeter host for both experiments"
  value       = aws_lb.main.dns_name
}

output "alb_usuarios_url" {
  description = "ASR16 latency experiment endpoint"
  value       = "http://${aws_lb.main.dns_name}/projects"
}

output "alb_reportes_url" {
  description = "ASR17 scalability experiment endpoint"
  value       = "http://${aws_lb.main.dns_name}/events/batch"
}

output "manejador_cloud_public_ip" {
  description = "manejador_cloud public IP — internal service, for SSH debugging only"
  value       = aws_instance.manejador_cloud.public_ip
}

output "redis_private_ip" {
  description = "Redis private IP — VPC-internal only"
  value       = aws_instance.redis.private_ip
}

output "rabbitmq_private_ip" {
  description = "RabbitMQ private IP — VPC-internal only"
  value       = aws_instance.rabbitmq.private_ip
}

output "rabbitmq_management_url" {
  description = "RabbitMQ management UI — accessible from within the VPC only"
  value       = "http://${aws_instance.rabbitmq.private_ip}:15672"
}

output "postgres_usuarios_private_ip" {
  value = aws_instance.postgres_usuarios.private_ip
}

output "postgres_cloud_private_ip" {
  value = aws_instance.postgres_cloud.private_ip
}

output "postgres_reportes_private_ip" {
  value = aws_instance.postgres_reportes.private_ip
}

output "worker_public_ips" {
  description = "Celery worker pool public IPs — for SSH debugging"
  value       = { for id, instance in aws_instance.worker_pool : id => instance.public_ip }
}

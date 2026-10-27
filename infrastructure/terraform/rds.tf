# ── RDS Subnet Group ──────────────────────────────────────────────────────────
resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id
  tags       = { Name = "${local.name_prefix}-db-subnet-group" }
}

# ── RDS PostgreSQL Instance ───────────────────────────────────────────────────
resource "aws_db_instance" "postgres" {
  identifier        = "${local.name_prefix}-postgres"
  engine            = "postgres"
  engine_version    = "15.4"
  instance_class    = local.is_prod ? "db.t3.micro" : "db.t3.micro"
  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = "cloudguard"
  username = "cgadmin"
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  backup_retention_period = local.is_prod ? 7 : 1
  backup_window           = "02:00-03:00"   # 07:30–08:30 IST
  maintenance_window      = "sun:04:00-sun:05:00"

  multi_az               = false   # Enable at 50+ customers
  deletion_protection    = local.is_prod
  skip_final_snapshot    = !local.is_prod
  final_snapshot_identifier = local.is_prod ? "${local.name_prefix}-final-snapshot" : null

  performance_insights_enabled = local.is_prod

  tags = { Name = "${local.name_prefix}-postgres" }
}

# ── ElastiCache Redis ─────────────────────────────────────────────────────────
resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name_prefix}-redis-subnet"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${local.name_prefix}-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.ecs.id]

  tags = { Name = "${local.name_prefix}-redis" }
}

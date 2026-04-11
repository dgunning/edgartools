data "aws_caller_identity" "current" {}

locals {
  name_prefix    = "edgartools-${var.environment}"
  container_name = "edgar-warehouse"
  tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "edgartools"
    },
    var.tags,
  )

  default_task_profiles = {
    small = {
      cpu    = 512
      memory = 1024
    }
    medium = {
      cpu    = 1024
      memory = 2048
    }
    large = {
      cpu    = 2048
      memory = 4096
    }
  }

  task_profiles = merge(local.default_task_profiles, var.task_profiles)

  default_task_profile_by_workflow = {
    daily_incremental   = "medium"
    bootstrap_recent_10 = "medium"
    bootstrap_full      = "large"
    targeted_resync     = "small"
    full_reconcile      = "medium"
  }

  task_profile_by_workflow = merge(local.default_task_profile_by_workflow, var.task_profile_by_workflow)

  workflows = {
    daily_incremental = {
      command             = ["daily-incremental"]
      task_profile        = local.task_profile_by_workflow.daily_incremental
      schedule_expression = var.daily_incremental_schedule
    }
    bootstrap_recent_10 = {
      command             = ["bootstrap-recent-10"]
      task_profile        = local.task_profile_by_workflow.bootstrap_recent_10
      schedule_expression = null
    }
    bootstrap_full = {
      command             = ["bootstrap-full"]
      task_profile        = local.task_profile_by_workflow.bootstrap_full
      schedule_expression = null
    }
    targeted_resync = {
      command             = ["targeted-resync"]
      task_profile        = local.task_profile_by_workflow.targeted_resync
      schedule_expression = null
    }
    full_reconcile = {
      command             = ["full-reconcile"]
      task_profile        = local.task_profile_by_workflow.full_reconcile
      schedule_expression = var.full_reconcile_schedule
    }
  }

  scheduled_workflows = {
    for name, workflow in local.workflows :
    name => workflow if workflow.schedule_expression != null
  }
}

resource "aws_ecr_repository" "warehouse" {
  name                 = "${local.name_prefix}-warehouse"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(local.tags, { Name = "${local.name_prefix}-warehouse" })
}

resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/aws/ecs/${local.name_prefix}-warehouse"
  retention_in_days = 30

  tags = local.tags
}

resource "aws_secretsmanager_secret" "edgar_identity" {
  count = var.edgar_identity_secret_arn == null ? 1 : 0

  name                    = "${local.name_prefix}-edgar-identity"
  description             = "SEC EDGAR identity string for warehouse jobs."
  recovery_window_in_days = 0

  tags = merge(local.tags, { Name = "${local.name_prefix}-edgar-identity" })
}

locals {
  resolved_edgar_identity_secret_arn = coalesce(
    var.edgar_identity_secret_arn,
    try(aws_secretsmanager_secret.edgar_identity[0].arn, null),
  )
}

resource "aws_ecs_cluster" "warehouse" {
  name = "${local.name_prefix}-warehouse"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(local.tags, { Name = "${local.name_prefix}-warehouse" })
}

resource "aws_iam_role" "ecs_task_execution" {
  name = "${local.name_prefix}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_managed" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_task_execution_secret" {
  name = "${local.name_prefix}-ecs-execution-secret"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = local.resolved_edgar_identity_secret_arn
      }
    ]
  })
}

resource "aws_iam_role" "ecs_task" {
  name = "${local.name_prefix}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy" "ecs_task_storage" {
  name = "${local.name_prefix}-ecs-storage"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          var.bronze_bucket_arn,
          var.warehouse_bucket_arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${var.bronze_bucket_arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${var.warehouse_bucket_arn}/*"
      }
    ]
  })
}

resource "aws_ecs_task_definition" "warehouse" {
  for_each = local.task_profiles

  family                   = "${local.name_prefix}-${each.key}"
  cpu                      = tostring(each.value.cpu)
  memory                   = tostring(each.value.memory)
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = local.container_name
      image     = coalesce(var.container_image, "scratch")
      essential = true
      command   = ["--help"]
      environment = [
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "WAREHOUSE_BRONZE_ROOT"
          value = "s3://${var.bronze_bucket_name}/warehouse/bronze"
        },
        {
          name  = "WAREHOUSE_STORAGE_ROOT"
          value = "s3://${var.warehouse_bucket_name}/warehouse"
        }
      ]
      secrets = [
        {
          name      = "EDGAR_IDENTITY"
          valueFrom = local.resolved_edgar_identity_secret_arn
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = each.key
        }
      }
    }
  ])

  tags = merge(local.tags, { TaskProfile = each.key })
}

resource "aws_iam_role" "step_functions" {
  name = "${local.name_prefix}-step-functions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy" "step_functions_runtime" {
  name = "${local.name_prefix}-step-functions-runtime"
  role = aws_iam_role.step_functions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:RunTask"
        ]
        Resource = [for task_definition in aws_ecs_task_definition.warehouse : task_definition.arn]
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:DescribeTasks",
          "ecs:StopTask"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = [
          aws_iam_role.ecs_task_execution.arn,
          aws_iam_role.ecs_task.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "events:PutTargets",
          "events:PutRule",
          "events:DescribeRule"
        ]
        Resource = "arn:aws:events:${var.aws_region}:${data.aws_caller_identity.current.account_id}:rule/StepFunctionsGetEventsForECSTaskRule"
      }
    ]
  })
}

resource "aws_sfn_state_machine" "workflow" {
  for_each = local.workflows

  name     = "${local.name_prefix}-${replace(each.key, "_", "-")}"
  role_arn = aws_iam_role.step_functions.arn

  definition = templatefile("${path.module}/templates/ecs_run_task.asl.json.tmpl", {
    cluster_arn         = aws_ecs_cluster.warehouse.arn
    task_definition_arn = aws_ecs_task_definition.warehouse[each.value.task_profile].arn
    container_name      = local.container_name
    command_json        = jsonencode(each.value.command)
    subnets_json        = jsonencode(var.subnet_ids)
    security_groups_json = jsonencode([var.security_group_id])
  })

  tags = merge(local.tags, { Workflow = each.key })
}

resource "aws_iam_role" "scheduler" {
  name = "${local.name_prefix}-scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy" "scheduler_start_execution" {
  name = "${local.name_prefix}-scheduler-start-execution"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution"
        ]
        Resource = [for workflow in aws_sfn_state_machine.workflow : workflow.arn]
      }
    ]
  })
}

resource "aws_scheduler_schedule" "workflow" {
  for_each = local.scheduled_workflows

  name                         = "${local.name_prefix}-${replace(each.key, "_", "-")}"
  description                  = "Schedule for ${each.key}"
  group_name                   = "default"
  schedule_expression          = each.value.schedule_expression
  schedule_expression_timezone = var.schedule_timezone
  state                        = "ENABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_sfn_state_machine.workflow[each.key].arn
    role_arn = aws_iam_role.scheduler.arn
    input = jsonencode({
      trigger  = "scheduler"
      workflow = each.key
    })
  }
}

resource "aws_cloudwatch_metric_alarm" "workflow_failures" {
  for_each = local.workflows

  alarm_name          = "${local.name_prefix}-${replace(each.key, "_", "-")}-failures"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_description   = "Alarm when ${each.key} fails."

  dimensions = {
    StateMachineArn = aws_sfn_state_machine.workflow[each.key].arn
  }
}


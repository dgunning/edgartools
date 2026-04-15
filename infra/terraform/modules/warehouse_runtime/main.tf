data "aws_caller_identity" "current" {}

locals {
  name_prefix                = "edgartools-${var.environment}"
  container_name             = "edgar-warehouse"
  database_name              = "EDGARTOOLS_${upper(var.environment)}"
  source_schema_name         = "EDGARTOOLS_SOURCE"
  gold_schema_name           = "EDGARTOOLS_GOLD"
  refresh_warehouse_name     = "EDGARTOOLS_${upper(var.environment)}_REFRESH_WH"
  runtime_role_name          = "EDGARTOOLS_${upper(var.environment)}_REFRESHER"
  stage_name                 = "EDGARTOOLS_SOURCE_EXPORT_STAGE"
  file_format_name           = "EDGARTOOLS_SOURCE_EXPORT_FILE_FORMAT"
  status_table_name          = "SNOWFLAKE_REFRESH_STATUS"
  source_load_procedure_name = "EDGARTOOLS_SOURCE.LOAD_EXPORTS_FOR_RUN"
  refresh_procedure_name     = "EDGARTOOLS_GOLD.REFRESH_AFTER_LOAD"
  snowflake_export_root      = "s3://${var.snowflake_export_bucket_name}/warehouse/artifacts/snowflake_exports"
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
    daily_incremental              = "medium"
    bootstrap_recent_10            = "medium"
    bootstrap_full                 = "large"
    targeted_resync                = "small"
    full_reconcile                 = "medium"
    load_daily_form_index_for_date = "small"
    catch_up_daily_form_index      = "small"
  }

  task_profile_by_workflow = merge(local.default_task_profile_by_workflow, var.task_profile_by_workflow)
  snowflake_task_profile   = local.task_profiles[var.snowflake_task_profile_name]

  workflows = {
    daily_incremental = {
      task_profile                 = local.task_profile_by_workflow.daily_incremental
      schedule_expression          = var.daily_incremental_schedule
      gold_affecting               = true
      warehouse_command_expression = "States.Array('daily-incremental', '--run-id', $$.Execution.Name)"
      snowflake_command_expression = "States.Array('snowflake-sync-after-load', '--workflow-name', 'daily_incremental', '--run-id', $$.Execution.Name)"
    }
    bootstrap_recent_10 = {
      task_profile                 = local.task_profile_by_workflow.bootstrap_recent_10
      schedule_expression          = null
      gold_affecting               = true
      warehouse_command_expression = "States.Array('bootstrap-recent-10', '--run-id', $$.Execution.Name)"
      snowflake_command_expression = "States.Array('snowflake-sync-after-load', '--workflow-name', 'bootstrap_recent_10', '--run-id', $$.Execution.Name)"
    }
    bootstrap_full = {
      task_profile                 = local.task_profile_by_workflow.bootstrap_full
      schedule_expression          = null
      gold_affecting               = true
      warehouse_command_expression = "States.Array('bootstrap-full', '--run-id', $$.Execution.Name)"
      snowflake_command_expression = "States.Array('snowflake-sync-after-load', '--workflow-name', 'bootstrap_full', '--run-id', $$.Execution.Name)"
    }
    targeted_resync = {
      task_profile                 = local.task_profile_by_workflow.targeted_resync
      schedule_expression          = null
      gold_affecting               = true
      warehouse_command_expression = "States.Array('targeted-resync', '--scope-type', $.scope_type, '--scope-key', $.scope_key, '--run-id', $$.Execution.Name)"
      snowflake_command_expression = "States.Array('snowflake-sync-after-load', '--workflow-name', 'targeted_resync', '--run-id', $$.Execution.Name)"
    }
    full_reconcile = {
      task_profile                 = local.task_profile_by_workflow.full_reconcile
      schedule_expression          = var.full_reconcile_schedule
      gold_affecting               = true
      warehouse_command_expression = "States.Array('full-reconcile', '--run-id', $$.Execution.Name)"
      snowflake_command_expression = "States.Array('snowflake-sync-after-load', '--workflow-name', 'full_reconcile', '--run-id', $$.Execution.Name)"
    }
    load_daily_form_index_for_date = {
      task_profile                 = local.task_profile_by_workflow.load_daily_form_index_for_date
      schedule_expression          = null
      gold_affecting               = false
      warehouse_command_expression = "States.Array('load-daily-form-index-for-date', $.target_date, '--run-id', $$.Execution.Name)"
      snowflake_command_expression = null
    }
    catch_up_daily_form_index = {
      task_profile                 = local.task_profile_by_workflow.catch_up_daily_form_index
      schedule_expression          = null
      gold_affecting               = false
      warehouse_command_expression = "States.Array('catch-up-daily-form-index', '--run-id', $$.Execution.Name)"
      snowflake_command_expression = null
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

resource "aws_cloudwatch_log_group" "step_functions" {
  name              = "/aws/states/${local.name_prefix}-warehouse"
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

resource "aws_secretsmanager_secret_version" "edgar_identity" {
  count = var.edgar_identity_secret_arn == null && var.edgar_identity_value != null ? 1 : 0

  secret_id     = aws_secretsmanager_secret.edgar_identity[0].id
  secret_string = var.edgar_identity_value
}

resource "aws_secretsmanager_secret" "snowflake_runtime" {
  count = var.snowflake_runtime_secret_arn == null ? 1 : 0

  name                    = "${local.name_prefix}-snowflake-runtime"
  description             = "WIF-only Snowflake runtime metadata for ${var.environment}."
  recovery_window_in_days = 0
  kms_key_id              = var.snowflake_export_kms_key_arn

  tags = merge(local.tags, { Name = "${local.name_prefix}-snowflake-runtime" })
}

resource "aws_secretsmanager_secret_version" "snowflake_runtime" {
  count = var.snowflake_runtime_secret_arn == null ? 1 : 0

  secret_id = aws_secretsmanager_secret.snowflake_runtime[0].id
  secret_string = jsonencode({
    account               = var.snowflake_account_identifier
    database              = local.database_name
    source_schema         = local.source_schema_name
    gold_schema           = local.gold_schema_name
    refresh_warehouse     = local.refresh_warehouse_name
    runtime_role          = local.runtime_role_name
    storage_integration   = var.snowflake_storage_integration_name
    stage_name            = local.stage_name
    file_format_name      = local.file_format_name
    status_table_name     = local.status_table_name
    source_load_procedure = local.source_load_procedure_name
    refresh_procedure     = local.refresh_procedure_name
  })

  lifecycle {
    precondition {
      condition = (
        var.snowflake_account_identifier != null &&
        trimspace(var.snowflake_account_identifier) != "" &&
        var.snowflake_storage_integration_name != null &&
        trimspace(var.snowflake_storage_integration_name) != ""
      )
      error_message = "snowflake_account_identifier and snowflake_storage_integration_name are required when snowflake_runtime_secret_arn is not provided."
    }
  }
}

locals {
  resolved_edgar_identity_secret_arn = coalesce(
    var.edgar_identity_secret_arn,
    try(aws_secretsmanager_secret.edgar_identity[0].arn, null),
  )
  resolved_snowflake_runtime_secret_arn = coalesce(
    var.snowflake_runtime_secret_arn,
    try(aws_secretsmanager_secret.snowflake_runtime[0].arn, null),
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

resource "aws_iam_role" "ecs_task_execution_warehouse" {
  name = "${local.name_prefix}-warehouse-execution"

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

resource "aws_iam_role_policy_attachment" "ecs_task_execution_warehouse_managed" {
  role       = aws_iam_role.ecs_task_execution_warehouse.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_task_execution_warehouse_secret" {
  name = "${local.name_prefix}-warehouse-execution-secret"
  role = aws_iam_role.ecs_task_execution_warehouse.id

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

resource "aws_iam_role" "ecs_task_execution_snowflake" {
  name = "${local.name_prefix}-snowflake-execution"

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

resource "aws_iam_role_policy_attachment" "ecs_task_execution_snowflake_managed" {
  role       = aws_iam_role.ecs_task_execution_snowflake.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_task_execution_snowflake_secret" {
  name = "${local.name_prefix}-snowflake-execution-secret"
  role = aws_iam_role.ecs_task_execution_snowflake.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = local.resolved_snowflake_runtime_secret_arn
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = var.snowflake_export_kms_key_arn
      },
    ]
  })
}

resource "aws_iam_role" "ecs_task_warehouse" {
  name = "${local.name_prefix}-warehouse-task"

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

resource "aws_iam_role_policy" "ecs_task_warehouse_storage" {
  name = "${local.name_prefix}-warehouse-storage"
  role = aws_iam_role.ecs_task_warehouse.id

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
          "s3:ListBucket"
        ]
        Resource = var.snowflake_export_bucket_arn
        Condition = {
          StringLike = {
            "s3:prefix" = [
              "warehouse/artifacts/snowflake_exports",
              "warehouse/artifacts/snowflake_exports/*"
            ]
          }
        }
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
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${var.snowflake_export_bucket_arn}/warehouse/artifacts/snowflake_exports/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = var.snowflake_export_kms_key_arn
      }
    ]
  })
}

resource "aws_iam_role" "ecs_task_snowflake" {
  name = "${local.name_prefix}-snowflake-task"

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

resource "aws_iam_role_policy" "ecs_task_snowflake_storage" {
  name = "${local.name_prefix}-snowflake-storage"
  role = aws_iam_role.ecs_task_snowflake.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = var.snowflake_export_bucket_arn
        Condition = {
          StringLike = {
            "s3:prefix" = [
              "warehouse/artifacts/snowflake_exports",
              "warehouse/artifacts/snowflake_exports/*"
            ]
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${var.snowflake_export_bucket_arn}/warehouse/artifacts/snowflake_exports/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = var.snowflake_export_kms_key_arn
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
  execution_role_arn       = aws_iam_role.ecs_task_execution_warehouse.arn
  task_role_arn            = aws_iam_role.ecs_task_warehouse.arn

  container_definitions = jsonencode([
    {
      name      = local.container_name
      image     = coalesce(var.container_image, "scratch")
      essential = true
      command   = ["--help"]
      environment = concat(
        [
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
          },
          {
            name  = "WAREHOUSE_RUNTIME_MODE"
            value = var.warehouse_runtime_mode
          },
          {
            name  = "SNOWFLAKE_EXPORT_ROOT"
            value = local.snowflake_export_root
          },
          {
            # Silver DuckDB must live on local container disk -- DuckDB cannot
            # read/write S3 paths directly.  /tmp is always writable on Fargate
            # and has 21 GB of ephemeral storage, which is more than enough for
            # a single-run DuckDB file.
            name  = "WAREHOUSE_SILVER_ROOT"
            value = "/tmp/edgar-warehouse-silver"
          }
        ],
        var.warehouse_bronze_cik_limit == null ? [] : [
          {
            name  = "WAREHOUSE_BRONZE_CIK_LIMIT"
            value = tostring(var.warehouse_bronze_cik_limit)
          }
        ]
      )
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
          awslogs-stream-prefix = "warehouse-${each.key}"
        }
      }
    }
  ])

  tags = merge(local.tags, { TaskProfile = each.key, Runtime = "warehouse" })
}

resource "aws_ecs_task_definition" "snowflake" {
  family                   = "${local.name_prefix}-snowflake-sync"
  cpu                      = tostring(local.snowflake_task_profile.cpu)
  memory                   = tostring(local.snowflake_task_profile.memory)
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_task_execution_snowflake.arn
  task_role_arn            = aws_iam_role.ecs_task_snowflake.arn

  container_definitions = jsonencode([
    {
      name      = local.container_name
      image     = coalesce(var.container_image, "scratch")
      essential = true
      command   = ["snowflake-sync-after-load", "--help"]
      environment = [
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "SNOWFLAKE_EXPORT_ROOT"
          value = local.snowflake_export_root
        }
      ]
      secrets = [
        {
          name      = "SNOWFLAKE_RUNTIME_METADATA"
          valueFrom = local.resolved_snowflake_runtime_secret_arn
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "snowflake-sync"
        }
      }
    }
  ])

  tags = merge(local.tags, { TaskProfile = var.snowflake_task_profile_name, Runtime = "snowflake-sync" })
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
        Resource = concat(
          [for task_definition in aws_ecs_task_definition.warehouse : task_definition.arn],
          [aws_ecs_task_definition.snowflake.arn],
        )
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
          aws_iam_role.ecs_task_execution_warehouse.arn,
          aws_iam_role.ecs_task_warehouse.arn,
          aws_iam_role.ecs_task_execution_snowflake.arn,
          aws_iam_role.ecs_task_snowflake.arn
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
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_sfn_state_machine" "workflow" {
  for_each = local.workflows

  name     = "${local.name_prefix}-${replace(each.key, "_", "-")}"
  role_arn = aws_iam_role.step_functions.arn

  definition = each.value.gold_affecting ? templatefile("${path.module}/templates/ecs_run_task_with_snowflake.asl.json.tmpl", {
    cluster_arn                   = aws_ecs_cluster.warehouse.arn
    warehouse_task_definition_arn = aws_ecs_task_definition.warehouse[each.value.task_profile].arn
    snowflake_task_definition_arn = aws_ecs_task_definition.snowflake.arn
    container_name                = local.container_name
    warehouse_command_expression  = each.value.warehouse_command_expression
    snowflake_command_expression  = each.value.snowflake_command_expression
    public_subnets_json           = jsonencode(var.public_subnet_ids)
    private_subnets_json          = jsonencode(var.private_subnet_ids)
    public_security_groups_json   = jsonencode([var.public_security_group_id])
    private_security_groups_json  = jsonencode([var.private_security_group_id])
    }) : templatefile("${path.module}/templates/ecs_run_task_single_step.asl.json.tmpl", {
    cluster_arn                  = aws_ecs_cluster.warehouse.arn
    task_definition_arn          = aws_ecs_task_definition.warehouse[each.value.task_profile].arn
    container_name               = local.container_name
    warehouse_command_expression = each.value.warehouse_command_expression
    subnets_json                 = jsonencode(var.public_subnet_ids)
    security_groups_json         = jsonencode([var.public_security_group_id])
  })

  logging_configuration {
    include_execution_data = true
    level                  = "ALL"
    log_destination        = "${aws_cloudwatch_log_group.step_functions.arn}:*"
  }

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

# ---------------------------------------------------------------------------
# Runner IAM user — may start and monitor Step Functions executions and read
# ECS task logs.  Must NOT have any infrastructure or S3 write permissions.
# Separate from the Terraform deployer account by design.
#
# Access keys are created manually:
#   aws iam create-access-key --user-name <runner-user-name>
# then stored in Secrets Manager:
#   secret name: <name_prefix>-runner-credentials
#   format: {"aws_access_key_id":"...","aws_secret_access_key":"...","aws_region":"..."}
# ---------------------------------------------------------------------------

resource "aws_secretsmanager_secret" "runner_credentials" {
  name                    = "${local.name_prefix}-runner-credentials"
  description             = "AWS access key credentials for the ${local.name_prefix}-runner IAM user (Step Functions trigger only). Value set out-of-band after key creation."
  recovery_window_in_days = 0

  tags = merge(local.tags, { Name = "${local.name_prefix}-runner-credentials", Role = "runner" })
}

resource "aws_iam_user" "runner" {
  name = "${local.name_prefix}-runner"
  tags = merge(local.tags, { Name = "${local.name_prefix}-runner", Role = "runner" })
}

resource "aws_iam_user_policy" "runner" {
  name = "${local.name_prefix}-runner"
  user = aws_iam_user.runner.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "StartWorkflows"
        Effect = "Allow"
        Action = ["states:StartExecution"]
        Resource = [for workflow in aws_sfn_state_machine.workflow : workflow.arn]
      },
      {
        Sid    = "MonitorWorkflows"
        Effect = "Allow"
        Action = [
          "states:DescribeExecution",
          "states:GetExecutionHistory",
          "states:DescribeStateMachine",
          "states:ListExecutions",
          "states:ListStateMachines"
        ]
        Resource = "*"
      },
      {
        Sid    = "ReadTaskLogs"
        Effect = "Allow"
        Action = [
          "logs:GetLogEvents",
          "logs:FilterLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "${aws_cloudwatch_log_group.ecs.arn}:*"
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

resource "aws_cloudwatch_log_metric_filter" "snowflake_sync_degraded" {
  name           = "${local.name_prefix}-snowflake-sync-degraded"
  log_group_name = aws_cloudwatch_log_group.step_functions.name
  pattern        = "SNOWFLAKE_SYNC_DEGRADED"

  metric_transformation {
    name      = "SnowflakeSyncDegraded"
    namespace = "EdgarTools/Warehouse"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "snowflake_sync_degraded" {
  alarm_name          = "${local.name_prefix}-snowflake-sync-degraded"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "SnowflakeSyncDegraded"
  namespace           = "EdgarTools/Warehouse"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_description   = "Alarm when Snowflake sync degrades after the canonical warehouse run succeeds."
}

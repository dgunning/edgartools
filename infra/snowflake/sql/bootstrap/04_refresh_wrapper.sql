-- Create the public Snowflake refresh wrapper for the EdgarTools gold mirror.
--
-- Required session variables:
--   set database_name = 'EDGARTOOLS_DEV';
--   set source_schema_name = 'EDGARTOOLS_SOURCE';
--   set gold_schema_name = 'EDGARTOOLS_GOLD';
--   set deployer_role_name = 'EDGARTOOLS_DEV_DEPLOYER';
--   set status_table_name = 'SNOWFLAKE_REFRESH_STATUS';
--   set source_load_procedure_name = 'EDGARTOOLS_SOURCE.LOAD_EXPORTS_FOR_RUN';
--   set refresh_procedure_name = 'REFRESH_AFTER_LOAD';

USE ROLE IDENTIFIER($deployer_role_name);
USE DATABASE IDENTIFIER($database_name);
USE SCHEMA IDENTIFIER($gold_schema_name);

CREATE OR REPLACE PROCEDURE IDENTIFIER($refresh_procedure_name)(workflow_name STRING, run_id STRING)
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
  load_result VARIANT;
BEGIN
  MERGE INTO EDGARTOOLS_SOURCE.SNOWFLAKE_REFRESH_STATUS AS target
  USING (
    SELECT
      CURRENT_DATABASE() AS environment,
      :workflow_name AS source_workflow,
      :run_id AS run_id,
      NULL::DATE AS business_date,
      'registered' AS source_load_status,
      'pending' AS refresh_status,
      'pending' AS status,
      NULL::STRING AS error_message,
      NULL::TIMESTAMP_TZ AS last_successful_refresh_at,
      CURRENT_TIMESTAMP() AS updated_at
  ) AS source
  ON target.environment = source.environment
    AND target.source_workflow = source.source_workflow
  WHEN MATCHED THEN UPDATE SET
    run_id = source.run_id,
    source_load_status = source.source_load_status,
    refresh_status = source.refresh_status,
    status = source.status,
    error_message = source.error_message,
    updated_at = source.updated_at
  WHEN NOT MATCHED THEN INSERT (
    environment,
    source_workflow,
    run_id,
    business_date,
    source_load_status,
    refresh_status,
    status,
    error_message,
    last_successful_refresh_at,
    updated_at
  ) VALUES (
    source.environment,
    source.source_workflow,
    source.run_id,
    source.business_date,
    source.source_load_status,
    source.refresh_status,
    source.status,
    source.error_message,
    source.last_successful_refresh_at,
    source.updated_at
  );

  load_result := OBJECT_CONSTRUCT(
    'status', 'registered',
    'workflow_name', :workflow_name,
    'run_id', :run_id
  );

  UPDATE EDGARTOOLS_SOURCE.SNOWFLAKE_REFRESH_STATUS
  SET
    refresh_status = 'ready_for_dbt_refresh',
    status = 'ready_for_dbt_refresh',
    updated_at = CURRENT_TIMESTAMP()
  WHERE environment = CURRENT_DATABASE()
    AND source_workflow = :workflow_name;

  RETURN OBJECT_CONSTRUCT(
    'status', 'ready_for_dbt_refresh',
    'workflow_name', :workflow_name,
    'run_id', :run_id,
    'load_result', load_result
  );
END;
$$;

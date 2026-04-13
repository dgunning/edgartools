-- Create the internal Snowflake refresh-status table.
--
-- Required session variables:
--   set database_name = 'EDGARTOOLS_DEV';
--   set source_schema_name = 'EDGARTOOLS_SOURCE';
--   set deployer_role_name = 'EDGARTOOLS_DEV_DEPLOYER';
--   set status_table_name = 'SNOWFLAKE_REFRESH_STATUS';

USE ROLE IDENTIFIER($deployer_role_name);
USE DATABASE IDENTIFIER($database_name);
USE SCHEMA IDENTIFIER($source_schema_name);

CREATE TABLE IF NOT EXISTS IDENTIFIER($status_table_name) (
  environment STRING NOT NULL,
  source_workflow STRING NOT NULL,
  run_id STRING NOT NULL,
  business_date DATE,
  source_load_status STRING NOT NULL,
  refresh_status STRING NOT NULL,
  status STRING NOT NULL,
  error_message STRING,
  last_successful_refresh_at TIMESTAMP_TZ,
  updated_at TIMESTAMP_TZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (environment, source_workflow)
)
COMMENT = 'Internal Snowflake mirror refresh status for EdgarTools.';

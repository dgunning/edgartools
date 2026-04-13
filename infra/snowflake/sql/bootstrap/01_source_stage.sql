-- Bootstrap the Snowflake-side S3 import path for EdgarTools export packages.
--
-- Required session variables:
--   set database_name = 'EDGARTOOLS_DEV';
--   set source_schema_name = 'EDGARTOOLS_SOURCE';
--   set deployer_role_name = 'EDGARTOOLS_DEV_DEPLOYER';
--   set storage_integration_name = 'EDGARTOOLS_DEV_S3_INTEGRATION';
--   set export_root_url = 's3://edgartools-dev-snowflake-export/warehouse/artifacts/snowflake_exports';
--   set stage_name = 'EDGARTOOLS_SOURCE_EXPORT_STAGE';
--   set file_format_name = 'EDGARTOOLS_SOURCE_EXPORT_FILE_FORMAT';

USE ROLE IDENTIFIER($deployer_role_name);
USE DATABASE IDENTIFIER($database_name);
USE SCHEMA IDENTIFIER($source_schema_name);

CREATE FILE FORMAT IF NOT EXISTS IDENTIFIER($file_format_name)
  TYPE = PARQUET
  COMPRESSION = AUTO;

CREATE STAGE IF NOT EXISTS IDENTIFIER($stage_name)
  URL = $export_root_url
  STORAGE_INTEGRATION = IDENTIFIER($storage_integration_name)
  FILE_FORMAT = IDENTIFIER($file_format_name)
  COMMENT = 'EdgarTools export stage used for Snowflake gold mirror imports.';

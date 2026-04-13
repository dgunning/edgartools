select
  environment,
  status,
  last_successful_refresh_at,
  business_date,
  source_workflow,
  run_id,
  updated_at
from {{ source("edgartools_source", "SNOWFLAKE_REFRESH_STATUS") }}

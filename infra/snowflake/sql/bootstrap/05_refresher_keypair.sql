-- 05_refresher_keypair.sql
--
-- Bind an RSA public key to the REFRESHER_USER for key-pair authentication.
-- This enables the ECS Snowflake sync task to authenticate without passwords.
--
-- Prerequisites:
--   1. Generate an RSA 2048-bit key pair:
--        openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
--        openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub
--   2. Store the private key PEM in Secrets Manager:
--        aws secretsmanager put-secret-value \
--          --secret-id edgartools-<env>-snowflake-private-key \
--          --secret-string "$(cat rsa_key.p8)" \
--          --profile edgartools-<env>
--   3. Extract the public key body (without BEGIN/END lines):
--        grep -v "PUBLIC KEY" rsa_key.pub | tr -d '\n'
--   4. Run this script with the public key body substituted below.
--
-- Session variables (set via SnowCLI --variable or SET):
--   $refresher_user_name  e.g. EDGARTOOLS_DEV_REFRESHER_USER
--
-- Usage:
--   snow sql -f 05_refresher_keypair.sql \
--     --variable "refresher_user_name=EDGARTOOLS_DEV_REFRESHER_USER"

USE ROLE ACCOUNTADMIN;

-- Replace <PUBLIC_KEY_BODY> with the base64-encoded public key (no BEGIN/END lines, no newlines).
ALTER USER IDENTIFIER($refresher_user_name)
  SET RSA_PUBLIC_KEY = '<PUBLIC_KEY_BODY>';

-- Verify the key fingerprint
DESC USER IDENTIFIER($refresher_user_name);
-- Look for RSA_PUBLIC_KEY_FP in the output.  It should show a SHA-256 fingerprint.

-- Optional: set a second key for zero-downtime rotation
-- ALTER USER IDENTIFIER($refresher_user_name)
--   SET RSA_PUBLIC_KEY_2 = '<ROTATED_PUBLIC_KEY_BODY>';

-- Runs once, on the first start of an empty volume (docker-entrypoint-initdb.d), as superuser `postgres`.
-- Roles follow docs/06-operations/01-database-operations.md and ADR-0005:
--   parksmart_owner    NOLOGIN, owns every object (migrations SET ROLE to it)
--   parksmart_migrator LOGIN, member of owner; used only by CI `migrate-dev-db`
--   parksmart_app      LOGIN, no BYPASSRLS, owns nothing; grants come from each migration
\set ON_ERROR_STOP on
\getenv migrator_pw MIGRATOR_PASSWORD
\getenv app_pw APP_PASSWORD

CREATE ROLE parksmart_owner NOLOGIN;
CREATE ROLE parksmart_migrator LOGIN PASSWORD :'migrator_pw' IN ROLE parksmart_owner;
CREATE ROLE parksmart_app LOGIN PASSWORD :'app_pw' NOBYPASSRLS;

CREATE DATABASE parksmart OWNER parksmart_owner;
REVOKE ALL ON DATABASE parksmart FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE parksmart TO parksmart_migrator, parksmart_app;

\connect parksmart
-- Extensions need superuser, so they are created here, not in migrations.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gist;
-- PG16: schema public is owned by pg_database_owner (= parksmart_owner) and PUBLIC has no CREATE on it.
GRANT USAGE ON SCHEMA public TO parksmart_app;

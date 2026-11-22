-- Cluster-level setup that revision 0001 needs but cannot do as parksmart_owner (no CREATEROLE). Runs as superuser
-- `postgres`: automatically on a fresh volume (after 01-roles.sql), and by hand once on an existing volume:
--   docker compose -f docker-compose.devdb.yml exec -T postgres \
--     psql -U postgres -d parksmart -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/02-runtime-roles.sql
-- Idempotent: safe to run again.
\set ON_ERROR_STOP on
\connect parksmart

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'parksmart_checkpointer') THEN
    CREATE ROLE parksmart_checkpointer NOLOGIN NOBYPASSRLS;   -- LangGraph saver, schema agent only
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'parksmart_readonly') THEN
    CREATE ROLE parksmart_readonly NOLOGIN NOBYPASSRLS;       -- ad-hoc analysis / future replica
  END IF;
END $$;

-- Session guard rails for the app role (docs/03-design/05-concurrency.md §0); ALTER ROLE … SET needs CREATEROLE.
ALTER ROLE parksmart_app SET statement_timeout = '5s';
ALTER ROLE parksmart_app SET lock_timeout = '2s';
ALTER ROLE parksmart_app SET idle_in_transaction_session_timeout = '30s';

-- 0001 runs ALTER DEFAULT PRIVILEGES FOR ROLE parksmart_checkpointer, which needs membership in that role.
-- The owner already owns every object, so acting as the checkpointer grants it nothing new.
GRANT parksmart_checkpointer TO parksmart_owner;

"""Alembic environment (ADR-0005): plain-SQL revisions via op.execute, no autogenerate.

URL: MIGRATE_DATABASE_URL (a role that may run DDL), else DATABASE_URL from settings. On the shared dev DB the
app role cannot run DDL, so a migration run by hand there fails instead of changing the schema; only CI migrates it.
MIGRATE_ROLE (e.g. parksmart_owner) is SET before migrating so every object is owned by the owner role
(docs/06-operations/01-database-operations.md).
"""

import os

from alembic import context
from sqlalchemy import create_engine, pool

from app.platform.config.settings import get_settings


def _url() -> str:
    url = os.environ.get("MIGRATE_DATABASE_URL") or get_settings().database_url
    # Plain postgresql:// would pick psycopg2; we ship psycopg 3.
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def run_migrations_offline() -> None:
    context.configure(url=_url(), literal_binds=True, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as conn:
        # Timeouts from the ops guide: a waiting DDL lock must not block the whole app.
        conn.exec_driver_sql("SET lock_timeout = '5s'")
        conn.exec_driver_sql("SET statement_timeout = '15min'")
        role = os.environ.get("MIGRATE_ROLE")
        if role:
            conn.exec_driver_sql(f'SET ROLE "{role}"')  # role name from CI config, not user input
        conn.commit()
        context.configure(connection=conn, target_metadata=None, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

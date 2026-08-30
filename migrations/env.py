from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, pool

from abuse_detector.db import Base, DEFAULT_DATABASE_URL

config = context.config
target_metadata = Base.metadata
database_url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url") or DEFAULT_DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with create_engine(database_url, poolclass=pool.NullPool).connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

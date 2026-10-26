"""Synchronous migration runner. DATABASE_URL is the single source of configuration."""

from alembic import context
from earthmind_api.models import Base
from earthmind_api.settings import Settings
from sqlalchemy import create_engine, pool

config = context.config
url = Settings().database_url.replace("postgresql://", "postgresql+psycopg://", 1)

if context.is_offline_mode():
    context.configure(
        url=url,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()

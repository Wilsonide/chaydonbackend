import asyncio  # <-- Added
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import (
    async_engine_from_config,  # <-- Switched to async variant
)

from alembic import context
from app.core.config import settings
from app.db.base import Base
from app.domains.auth.models import RefreshSession
from app.domains.customers.models import Customer
from app.domains.inventory.models import *
from app.domains.invoices.models import Invoice
from app.domains.orders.models import Order
from app.domains.payments.models import Payment
from app.domains.production.models import (
    ProductionActivity,
    ProductionFile,
    ProductionFolder,
)
from app.domains.tasks.models import (
    Task,
    TaskComment,
)
from app.domains.users.credential_model import UserCredential
from app.domains.users.models import User

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):  # <-- Added sync worker function
    """Configure connection context and run the actual migrations."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:  # <-- Changed to async def
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # run_sync opens a safe synchronous portal for Alembic's commands
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    # Trigger the async runner inside a fresh event loop
    asyncio.run(run_migrations_online())

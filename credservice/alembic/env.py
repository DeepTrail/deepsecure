"""Alembic environment configuration script."""

import logging
from logging.config import fileConfig
import os
import sys
from dotenv import load_dotenv

from sqlalchemy import engine_from_config, create_engine
from sqlalchemy import pool

from alembic import context

# Load .env file specifically for Alembic context
# Adjust path if alembic is not run from project root
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add project directory to sys.path
# Assuming alembic is run from the project root (credservice)
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

# Import Base from your models module
# Make sure your models are defined and importable
# Example: from app.models.user import Base # Adjust path as needed
from app.db.base import Base
target_metadata = Base.metadata # Restore original line
# target_metadata = None # Temporarily set to None for testing

# other values from the config, defined by the needs of env.py,
# can be acquired: my_important_option = config.get_main_option("my_important_option")
# ... etc.

def get_url():
    # Always get URL from environment, ensure .env is loaded first
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        # Fallback or raise error if not found
        # For autogenerate, it might be okay to use a dummy default if needed,
        # but preferable to require .env to be set up.
        raise ValueError("DATABASE_URL environment variable not set. Please configure .env file.")
    return db_url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Ensure psycopg2 is importable after potential sys.path changes
    try:
        import psycopg2
    except ImportError:
        logging.error("psycopg2 not found after sys.path modification in env.py")
        raise

    # Directly use get_url() instead of reading from config section
    connectable = create_engine(get_url())

    # --- OR --- (Alternative using engine_from_config but forcing URL)
    # configuration = config.get_section(config.config_ini_section)
    # configuration["sqlalchemy.url"] = get_url() # Force URL from environment
    # connectable = engine_from_config(
    #     configuration,
    #     prefix="sqlalchemy.",
    #     poolclass=pool.NullPool,
    # )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online() 
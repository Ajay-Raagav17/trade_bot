import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# --- START Custom Additions ---
# Add project parent directory (e.g., /app for trading_bot_backend) to sys.path
# This allows Alembic to find 'trading_bot_backend.models'
# __file__ is alembic/env.py. dirname(__file__) is alembic/. '..' is trading_bot_backend. '..' again is /app.
project_parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_parent_dir not in sys.path:
    sys.path.insert(0, project_parent_dir)

from trading_bot_backend.models import Base # Path to your models.py

# Get DATABASE_URL from environment variable first
DB_URL_FOR_ALEMBIC = os.getenv('DATABASE_URL')
# --- END Custom Additions ---

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line needs to be positioned at the top of the script.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- START Custom Modification for DB_URL ---
# If DB_URL_FOR_ALEMBIC from env is not set, try to get it from alembic.ini as a fallback
if not DB_URL_FOR_ALEMBIC:
    print("ALEMBIC_ENV.PY INFO: DATABASE_URL environment variable not set. "
          "Attempting to use sqlalchemy.url from alembic.ini.")
    DB_URL_FOR_ALEMBIC = config.get_main_option("sqlalchemy.url") # This uses the value from alembic.ini

if not DB_URL_FOR_ALEMBIC or "${DATABASE_URL}" in DB_URL_FOR_ALEMBIC: # Check if it's still the placeholder from ini
    # This will cause a failure if no URL is configured either via ENV or alembic.ini having a real value
    print(f"ALEMBIC_ENV.PY ERROR: Database URL is not properly configured. Current value: {DB_URL_FOR_ALEMBIC}")
    print("Ensure DATABASE_URL environment variable is set, or sqlalchemy.url in alembic.ini has a valid connection string.")
    # To allow autogenerate to proceed without a live DB for this subtask, we might set a default placeholder here if it's truly unresolved.
    # However, the bash script `export DATABASE_URL=...` should prevent this in the autogen step.
    # If this script is run by `alembic upgrade` later, that env var must be set.
    if DB_URL_FOR_ALEMBIC == "${DATABASE_URL}": # Explicitly check for the env var placeholder string
        print("ALEMBIC_ENV.PY: sqlalchemy.url is still the placeholder ${DATABASE_URL}. This means the env var was not substituted by alembic.ini itself.")
        # This indicates an issue if alembic.ini was expected to resolve it.
        # Forcing a placeholder to allow script to run, but this is not ideal for real operations.
        DB_URL_FOR_ALEMBIC = "postgresql://placeholder_user:placeholder_pass@placeholder_host:5432/placeholder_db_for_alembic_env_py"
        print(f"ALEMBIC_ENV.PY: Using internal placeholder for autogen: {DB_URL_FOR_ALEMBIC}")


# Set the sqlalchemy.url in the config object for other parts of Alembic that might use it,
# prioritizing the one we've determined (from env or ini).
if DB_URL_FOR_ALEMBIC:
    config.set_main_option("sqlalchemy.url", DB_URL_FOR_ALEMBIC)
else:
    # This should ideally not be reached if the above logic or env var export works.
    raise ValueError("Alembic env.py: Database URL could not be resolved.")

# --- END Custom Modification for DB_URL ---

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata # Use Base.metadata from our models

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
    url = config.get_main_option("sqlalchemy.url") # This will now use the URL we set via set_main_option
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
    # config.get_section(config.config_ini_section) will use the sqlalchemy.url we set via set_main_option
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

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

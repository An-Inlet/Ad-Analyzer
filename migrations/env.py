from logging.config import fileConfig

import app.billing.models  # noqa: F401
import app.campaign_review.models  # noqa: F401
import app.customer_context.models  # noqa: F401
import app.google_connections.models  # noqa: F401
from alembic import context
from app.ads import models  # noqa: F401
from app.analysis import models as analysis_models  # noqa: F401
from app.automation import models as automation_models  # noqa: F401
from app.customers import models as customer_models  # noqa: F401
from app.database.session import Base
from app.goals import models as goal_models  # noqa: F401
from app.imports import models as import_models  # noqa: F401
from app.intelligence import models as intelligence_models  # noqa: F401
from app.mandates import models as mandate_models  # noqa: F401
from app.measurement import models as measurement_models  # noqa: F401
from app.meta import models as meta_models  # noqa: F401
from app.settings import settings
from app.shopify import models as shopify_models  # noqa: F401
from app.sources import models as source_models  # noqa: F401
from sqlalchemy import engine_from_config, pool

config = context.config
resolved_database_url = settings.resolved_database_url
config.set_main_option(
    "sqlalchemy.url", resolved_database_url.render_as_string(hide_password=False).replace("%", "%%")
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without creating an engine."""
    context.configure(
        url=resolved_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

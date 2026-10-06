"""Read-only database dependency check, separate from process liveness."""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from app.settings import settings


def database_available(url: URL | None = None) -> bool:
    """Use a fresh connection so application pool exhaustion cannot stall the probe.

    PostgreSQL bounds connection establishment and statements independently. These
    are not a universal wall-clock bound on DNS or operating-system networking.
    Nothing is written and no provider APIs are consulted.
    """
    target = url if url is not None else settings.resolved_database_url
    if target.drivername not in {"postgresql", "postgresql+psycopg", "postgresql+psycopg2"}:
        return False
    engine = None
    try:
        engine = create_engine(
            target.set(drivername="postgresql+psycopg"),
            poolclass=NullPool,
            connect_args={
                "connect_timeout": 2,
                "options": (
                    "-c statement_timeout=1000 -c lock_timeout=500 "
                    "-c default_transaction_read_only=on"
                ),
            },
            hide_parameters=True,
        )
        with engine.connect() as connection:
            return bool(connection.scalar(text("SELECT 1")) == 1)
    except (SQLAlchemyError, ValueError):
        # Database addresses, credentials and driver messages never enter a response/log.
        return False
    finally:
        if engine is not None:
            engine.dispose()

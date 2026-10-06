"""Use the same complete ORM graph as Alembic and application startup."""

from app.database.models import register_models

register_models()

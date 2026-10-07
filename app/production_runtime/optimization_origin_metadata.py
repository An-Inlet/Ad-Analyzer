"""Keep the cyclic origin FK reusable across metadata creation dialects."""

from typing import Any

from sqlalchemy import Connection, ForeignKeyConstraint, Table, event


def register(table: Table) -> None:
    constraint = next(
        item
        for item in table.constraints
        if isinstance(item, ForeignKeyConstraint) and item.name == "fk_optimization_origin_digest"
    )

    def restore_inline_rule(target: Table, connection: Connection, **kwargs: Any) -> None:
        # SQLAlchemy's PostgreSQL SchemaGenerator constructs AddConstraint with
        # isolate_from_table=True. That mutates this shared constraint's private
        # DDL rule permanently, even if ALTER fails. A later SQLite CREATE then
        # silently omits the FK (SQLite cannot ALTER it back). Reset only this
        # model-owned rule before creation. use_alter still controls PostgreSQL
        # ordering; names, deferral, referential semantics and migrations stay exact.
        constraint._create_rule = None

    event.listen(table, "before_create", restore_inline_rule)

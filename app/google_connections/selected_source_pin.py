"""Private, transaction-local connection binding; never a customer-facing receipt."""

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.google_connections.models import GoogleCustomerConnection


@dataclass(frozen=True, repr=False)
class SourcePin:
    source_id: str
    encrypted_grant: str
    login_customer_id: str | None

    def grant(self) -> tuple[str, str | None]:
        return self.encrypted_grant, self.login_customer_id


def source_pin(db: Session, workspace_id: int, account_id: int) -> SourcePin:
    # Caller holds original-session/workspace authority. This adds no authority.
    row = db.scalar(
        select(GoogleCustomerConnection)
        .where(
            GoogleCustomerConnection.workspace_id == workspace_id,
            GoogleCustomerConnection.account_id == account_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None or not row.encrypted_grant:
        raise HTTPException(409, "reporting_connection_unavailable")
    return SourcePin(row.id, row.encrypted_grant, row.login_customer_id)

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class CustomerUser(Base):
    __tablename__ = "customer_users"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_customer_identity"),
        CheckConstraint("status IN ('active', 'suspended')", name="ck_customer_user_status"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")


class CustomerSession(Base):
    __tablename__ = "customer_sessions"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("customer_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    csrf_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    authenticated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    revoked_at: Mapped[int | None] = mapped_column(BigInteger)


class CustomerTokenExchange(Base):
    """One-time ID-token exchange receipt. Never store the provider token."""

    __tablename__ = "customer_token_exchanges"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)


class CustomerMembership(Base):
    """Customer-only membership; existing operator/email memberships stay separate."""

    __tablename__ = "customer_memberships"
    __table_args__ = (
        CheckConstraint("role IN ('owner','admin','analyst','viewer')", name="ck_customer_role"),
        CheckConstraint("status IN ('active','suspended')", name="ck_customer_membership_status"),
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("customer_users.id", ondelete="CASCADE"), primary_key=True
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")


class WorkspaceSignup(Base):
    __tablename__ = "customer_workspace_signups"
    user_id: Mapped[str] = mapped_column(
        ForeignKey("customer_users.id", ondelete="CASCADE"), primary_key=True
    )
    key_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, unique=True
    )

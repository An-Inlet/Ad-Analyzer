"""Customer flow receipts; no token or provider calls escape current actor checks."""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update

from app.meta.client import unpack_page
from app.meta.models import MetaAudit, MetaOAuthState, MetaPendingGrant
from app.meta.normalize import account_metadata
from app.meta.security import SCOPES, MetaError, Vault
from app.meta.service import ConnectionService, credentials
from app.workspaces.models import Workspace


def workspace_lock(service: ConnectionService, wid: int) -> None:
    service.session.scalar(select(Workspace).where(Workspace.id == wid).with_for_update())


def bound_grant(
    service: ConnectionService, wid: int, actor: str, state: str, now: datetime
) -> MetaPendingGrant:
    grant = service.grant(wid, actor, now, lock=True)
    if grant is None or grant.oauth_state_digest != Vault(service.settings).digest("state", state):
        raise MetaError("meta_authorization_expired")
    return grant


def finish(
    service: ConnectionService,
    state: MetaOAuthState,
    code: str,
    role: str,
    now: Callable[[], datetime],
    guard: Callable[[], None],
) -> None:
    db = service.session
    wid, actor, nonce = state.workspace_id, state.actor_digest, state.digest
    workspace_lock(service, wid)
    connected = service.get(wid, lock=True)
    generation = (connected.id, connected.generation) if connected else None
    result = db.execute(
        update(MetaOAuthState)
        .execution_options(synchronize_session="fetch")
        .where(
            MetaOAuthState.digest == nonce,
            MetaOAuthState.phase == "pending",
            MetaOAuthState.expires_at > now(),
        )
        .values(phase="exchanging")
    )
    if result.rowcount != 1:  # type: ignore[attr-defined]
        raise MetaError("invalid_oauth_state")
    db.commit()

    def checkpoint() -> MetaOAuthState:
        guard()
        current = service.get(wid, lock=True)
        if ((current.id, current.generation) if current else None) != generation:
            raise MetaError("invalid_oauth_state")
        row = db.scalar(
            select(MetaOAuthState)
            .where(
                MetaOAuthState.digest == nonce,
                MetaOAuthState.workspace_id == wid,
                MetaOAuthState.actor_digest == actor,
                MetaOAuthState.phase == "exchanging",
                MetaOAuthState.expires_at > now(),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise MetaError("invalid_oauth_state")
        return row

    try:
        short = credentials(service.client.token(code=code), now())
        checkpoint()
        db.commit()
        bundle = credentials(service.client.token(exchange_token=short["access_token"]), now())
        checkpoint()
        db.commit()
        permissions, cursor = unpack_page(service.client.permissions(bundle["access_token"]))
        checkpoint()
        granted = {p.get("permission") for p in permissions if p.get("status") == "granted"}
        if not granted >= SCOPES or "ads_management" in granted or cursor:
            raise MetaError("meta_read_only_scope_required")
        db.commit()
        items, cursor = unpack_page(service.client.accounts(bundle["access_token"]))
        row = checkpoint()
        db.add(
            MetaPendingGrant(
                workspace_id=wid,
                actor_digest=actor,
                oauth_state_digest=nonce,
                expires_at=now() + timedelta(minutes=10),
                encrypted_credentials=Vault(service.settings).seal(wid, "grant:" + actor, bundle),
                accounts=[account_metadata(item) for item in items],
                cursor=cursor,
            )
        )
        db.delete(row)
        db.add(MetaAudit(workspace_id=wid, action="authorized", actor_role=role))
        db.commit()
    except Exception:
        db.rollback()
        workspace_lock(service, wid)
        db.execute(
            update(MetaOAuthState)
            .execution_options(synchronize_session="fetch")
            .where(MetaOAuthState.digest == nonce, MetaOAuthState.phase == "exchanging")
            .values(phase="failed")
        )
        db.commit()
        raise


def more_accounts(
    service: ConnectionService,
    wid: int,
    actor: str,
    state: str,
    now: Callable[[], datetime],
    guard: Callable[[], None],
) -> MetaPendingGrant:
    grant = bound_grant(service, wid, actor, state, now())
    if not grant.cursor:
        return grant
    gid, previous = grant.id, grant.cursor
    bundle = Vault(service.settings).open(
        wid, "grant:" + grant.actor_digest, grant.encrypted_credentials
    )
    service.session.commit()
    response: dict[str, Any] = service.client.accounts(bundle["access_token"], previous)
    guard()
    grant = bound_grant(service, wid, actor, state, now())
    if grant.id != gid or grant.cursor != previous:
        raise MetaError("meta_authorization_expired")
    items, cursor = unpack_page(response, previous)
    grant.accounts, grant.cursor = [account_metadata(item) for item in items], cursor
    service.session.commit()
    return grant

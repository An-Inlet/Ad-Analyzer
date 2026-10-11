"""Original-session private image inspection, independent of planner activation."""

import hashlib
import math
from collections.abc import Callable
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing.entitlements import paid_work
from app.campaign_review.contracts import MediaStore
from app.campaign_review.models import MediaObject
from app.campaign_review.service import inspect_media
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.lifecycle.privacy import workspace_export_revision
from app.planning_documents.creative_basis import (
    CreativeBasisV1,
    CreativeInputV1,
    OwnedPlanningImageV1,
)
from app.planning_documents.creative_image_collection import (
    CollectedCreativeBasisV1,
    PlanningImageRowPinV1,
)
from app.planning_documents.ports import GenerationTicket
from app.planning_documents.read_context import PlanningReadContexts, snapshot
from app.planning_documents.repository import check_goal
from app.shopify.security import utc


class PlanningImageUnavailable(ValueError):
    def __init__(self) -> None:
        super().__init__("owned planning image evidence unavailable")


def _validated[Model: BaseModel](model: type[Model], value: Any) -> Model:
    """Only pure DTO parsing errors are expected media-evidence failures."""
    try:
        return model.model_validate(value)
    except ValidationError:
        raise PlanningImageUnavailable() from None


class OwnedPlanningImageReader:
    def __init__(
        self,
        sessions: Callable[[], Session],
        *,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        store: MediaStore,
        clock: Callable[[], datetime],
    ) -> None:
        self.sessions, self.principal = sessions, snapshot(principal)
        self.provider, self.store, self.clock = provider, store, clock

    def collect(self, ticket: GenerationTicket, requested: CreativeInputV1) -> CreativeBasisV1:
        return self._collect(ticket, requested, pinned=False).basis

    def collect_pinned(
        self, ticket: GenerationTicket, requested: CreativeInputV1
    ) -> CollectedCreativeBasisV1:
        # Reject unsaved/substituted intent before any identity-provider or storage IO.
        ticket = _validated(GenerationTicket, ticket)
        requested = _validated(CreativeInputV1, requested)
        if ticket.inputs.creative is None or ticket.inputs.creative != requested:
            raise PlanningImageUnavailable()
        return self._collect(ticket, requested, pinned=True)

    def _collect(
        self, ticket: GenerationTicket, requested: CreativeInputV1, *, pinned: bool
    ) -> CollectedCreativeBasisV1:
        started = last_tick = monotonic()
        last_wall: datetime | None = None

        def checkpoint() -> datetime:
            nonlocal last_tick, last_wall
            current = monotonic()
            if (
                not math.isfinite(current)
                or not math.isfinite(started)
                or not last_tick <= current < started + 60
            ):
                raise PlanningImageUnavailable()
            last_tick = current
            now = self.clock()
            if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                raise PlanningImageUnavailable()
            now = now.astimezone(UTC)
            if last_wall is not None and now < last_wall:
                raise PlanningImageUnavailable()
            last_wall = now
            return now

        checkpoint()
        ticket = _validated(GenerationTicket, ticket)
        requested = _validated(CreativeInputV1, requested)
        if (ticket.actor_id, ticket.session_digest) != (
            self.principal.user.id,
            self.principal.session.digest,
        ):
            raise HTTPException(401, "original customer session required")
        wid = ticket.inputs.workspace_id
        reads = PlanningReadContexts(
            self.sessions, self.principal, self.provider, wid, ticket.actor_id
        )

        def goal(db: Session) -> None:
            try:
                check_goal(db, ticket.inputs, checkpoint())
            except HTTPException as error:
                if error.status_code != 409:
                    raise
                raise PlanningImageUnavailable() from None

        def rows() -> tuple[PlanningImageRowPinV1, ...]:
            with reads.open() as db:
                paid_work(db, wid, checkpoint())
                goal(db)
                if workspace_export_revision(db, wid) != ticket.privacy_revision:
                    raise PlanningImageUnavailable()
                result = []
                for selected in requested.media_selections:
                    row = db.scalar(
                        select(MediaObject)
                        .where(MediaObject.workspace_id == wid, MediaObject.id == selected.media_id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                    if row is None or row.sha256 != selected.expected_sha256:
                        raise PlanningImageUnavailable()
                    result.append(
                        _validated(
                            PlanningImageRowPinV1,
                            dict(
                                created_by=row.created_by,
                                witness=dict(
                                    workspace_id=row.workspace_id,
                                    media_id=row.id,
                                    sha256=row.sha256,
                                    size=row.size,
                                    mime=row.mime,
                                    width=row.width,
                                    height=row.height,
                                    created_at=utc(row.created_at),
                                    observed_at=checkpoint(),
                                    privacy_revision=ticket.privacy_revision,
                                ),
                            ),
                        )
                    )
                # Resample after all goal/store/media locks, including on empty input.
                goal(db)
                paid_work(db, wid, checkpoint())
                if workspace_export_revision(db, wid) != ticket.privacy_revision:
                    raise PlanningImageUnavailable()
            checkpoint()  # Context exit itself performs a final authority check.
            return tuple(result)

        original = rows()
        # Validate exact order, currency and total library size BEFORE private I/O.
        basis = _validated(
            CreativeBasisV1,
            dict(
                workspace_id=wid,
                goal_currency=ticket.inputs.goal.definition.target_window.currency,
                privacy_revision=ticket.privacy_revision,
                requested=requested,
                images=tuple(row.witness for row in original),
            ),
        )
        images = []
        for row in original:
            image = row.witness
            checkpoint()
            try:
                data = self.store.read_exact(wid, image.sha256, image.size)
            except (OSError, ValueError):
                raise PlanningImageUnavailable() from None
            checkpoint()
            if (
                type(data) is not bytes
                or len(data) != image.size
                or hashlib.sha256(data).hexdigest() != image.sha256
                or data[4:8] == b"ftyp"
            ):
                raise PlanningImageUnavailable()
            checkpoint()
            try:
                inspected = inspect_media(data)
            except HTTPException as error:
                if error.status_code not in {413, 422}:
                    raise
                raise PlanningImageUnavailable() from None
            if inspected != (image.mime, image.width, image.height):
                raise PlanningImageUnavailable()
            observed = checkpoint()
            del data
            images.append(
                _validated(OwnedPlanningImageV1, image.model_copy(update={"observed_at": observed}))
            )
        final = rows()
        if tuple(row.identity() for row in original) != tuple(row.identity() for row in final):
            raise PlanningImageUnavailable()
        result = _validated(CreativeBasisV1, basis.model_copy(update={"images": tuple(images)}))
        pins = tuple(
            _validated(PlanningImageRowPinV1, dict(witness=image, created_by=row.created_by))
            for image, row in zip(result.images, original, strict=True)
        )
        envelope = _validated(
            CollectedCreativeBasisV1,
            dict(basis=result, rows=pins, ticket_digest=ticket.digest()),
        )
        if pinned:
            envelope.assert_ticket(ticket)
        checkpoint()
        return envelope

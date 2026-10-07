"""Append-only original Google execution evidence and owned nonfinancial projection."""

from collections.abc import Callable
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.publication import activation, coordinator
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import Environment
from app.publication.execution_models import (
    GoogleOriginalCompletion,
    ProviderExecutionAttempt,
    ProviderExecutionResponse,
    ProviderExecutionReview,
    ProviderExecutionRun,
)
from app.publication.google_completion import read_owned as read_optimization_completion
from app.publication.google_execution_completion_contracts import (
    GoogleCapturedActivationResponse,
    GoogleCapturedCreationResponse,
    GoogleExecutionCompletionV2,
    GoogleExecutionRequest,
    OriginalOperationCompletionView,
    parse_completion,
)
from app.publication.provider_contracts import BoundProviderRequest
from app.shopify.security import utc


def capture_execution_response(
    db: Session,
    request: GoogleExecutionRequest,
    response: GoogleCapturedCreationResponse | GoogleCapturedActivationResponse,
    attempt: ProviderExecutionAttempt,
    environment: Environment,
    response_digest: str,
    now: datetime,
) -> None:
    """No commit: caller holds original evidence locks, response and capture are atomic."""
    if response.outcome != "acknowledged" or response.request_digest != request.digest():
        raise HTTPException(409, "original Google response unavailable")
    document = GoogleExecutionCompletionV2(
        capture=response.capture,
        environment=environment,
        attempt_id=attempt.id,
        run_id=attempt.run_id,
        step_id=attempt.step_id,
        normalized_response_digest=response_digest,
        recorded_at=now,
    )
    try:
        document.bind(request, now)
        if (
            attempt.workspace_id != document.capture.account.workspace_id
            or attempt.request_digest != request.digest()
            or attempt.fence != request.fence
        ):
            raise ValueError()
        prior = db.get(GoogleOriginalCompletion, attempt.id)
        if prior is not None:
            old = parse_completion(prior.document)
            if not isinstance(old, GoogleExecutionCompletionV2):
                raise ValueError()
            old.bind(request, now)
            if (
                old.model_dump(exclude={"recorded_at"})
                != document.model_dump(exclude={"recorded_at"})
                or old.digest() != prior.digest
                or prior.workspace_id != attempt.workspace_id
                or prior.request_digest != request.digest()
                or prior.fence != request.fence
                or utc(prior.recorded_at) != old.recorded_at
            ):
                raise ValueError()
            return
    except ValueError:
        raise HTTPException(409, "immutable original Google response changed") from None
    db.add(
        GoogleOriginalCompletion(
            attempt_id=attempt.id,
            workspace_id=attempt.workspace_id,
            fence=request.fence,
            request_digest=request.digest(),
            digest=document.digest(),
            document=document.model_dump(mode="json"),
            recorded_at=now,
        )
    )


def read_execution_completion(
    db: Session,
    workspace_id: int,
    attempt_id: str,
    actor: str,
    *,
    authorize: Callable[[], None],
    clock: Callable[[], datetime],
) -> OriginalOperationCompletionView:
    """Historical read only. Missing/contradictory evidence never releases any obligation."""
    authorize()
    result = _read(db, workspace_id, attempt_id, actor, clock)
    authorize()  # Original session/role/expiry after all potentially blocking evidence reads.
    return result


def _read(
    db: Session, wid: int, attempt_id: str, actor: str, clock: Callable[[], datetime]
) -> OriginalOperationCompletionView:
    unavailable = OriginalOperationCompletionView()
    receipt = coordinator.read_owned_outcome_receipt(db, wid, attempt_id, actor)
    if receipt is None or receipt.outcome not in {"verified_effect", "verified_target_state"}:
        return unavailable
    raw = db.scalar(
        select(ProviderExecutionReview.document)
        .join(ProviderExecutionRun, ProviderExecutionRun.review_id == ProviderExecutionReview.id)
        .join(ProviderExecutionAttempt, ProviderExecutionAttempt.run_id == ProviderExecutionRun.id)
        .where(
            ProviderExecutionAttempt.id == attempt_id,
            ProviderExecutionAttempt.workspace_id == wid,
            ProviderExecutionRun.workspace_id == wid,
            ProviderExecutionReview.workspace_id == wid,
        )
    )
    if raw is None:
        raise HTTPException(404, "provider attempt unavailable")
    purpose = raw.get("purpose")
    if purpose == "existing_campaign_optimize":
        if receipt.account.account.platform != "google_ads":
            return unavailable
        old = read_optimization_completion(db, wid, attempt_id, actor, clock())
        if old is None:
            return unavailable
        from app.publication.optimization_contracts import OptimizationResponse

        expected = OptimizationResponse(
            request_digest=old.capture.request_digest, outcome="acknowledged"
        ).model_dump(mode="json")
        response_digest = fingerprint("inlet.optimization-response.v1", expected)
        original_response = db.get(ProviderExecutionResponse, (attempt_id, response_digest))
        if (
            old.capture.account != receipt.account
            or old.capture.fence != receipt.fence
            or old.capture.request_digest != receipt.request_digest
            or old.capture.resource_name != receipt.resource_name
            or original_response is None
            or original_response.workspace_id != wid
            or original_response.response != expected
        ):
            raise HTTPException(409, "original Google response evidence changed")
        return OriginalOperationCompletionView(
            status="completed",
            purpose="existing_campaign_optimize",
            profile=old.capture.profile,
            commitment=old.digest(),
        )
    request: GoogleExecutionRequest
    if purpose == "activate":
        run, review, attempt, request = activation.evidence_lock(db, wid, attempt_id)
        environment = review.mandate.environment
    else:
        run, creation_review, attempt, creation_request = coordinator.evidence_lock(
            db, wid, attempt_id
        )
        if not isinstance(creation_request, BoundProviderRequest):
            return unavailable
        request = creation_request
        environment = creation_review.mandate.environment
    row = db.get(GoogleOriginalCompletion, attempt_id)
    if row is None:
        return unavailable
    try:
        document = parse_completion(row.document)
        if not isinstance(document, GoogleExecutionCompletionV2):
            raise ValueError()
        document.bind(request, clock())
        if (
            document.attempt_id != attempt.id
            or document.run_id != run.id
            or document.step_id != attempt.step_id
            or document.environment != environment
            or row.workspace_id != wid
            or row.request_digest != request.digest()
            or row.fence != request.fence
            or row.digest != document.digest()
            or utc(row.recorded_at) != document.recorded_at
            or document.capture.account != receipt.account
            or document.capture.request_digest != receipt.request_digest
            or document.capture.fence != receipt.fence
            or document.capture.resource_name != receipt.resource_name
        ):
            raise ValueError()
        response = db.get(
            ProviderExecutionResponse, (attempt.id, document.normalized_response_digest)
        )
        if response is None or response.workspace_id != wid:
            raise ValueError()

        domain = (
            "inlet.activation-response.v1"
            if purpose == "activate"
            else "inlet.provider-response.v1"
        )
        if (
            fingerprint(domain, response.response) != response.digest
            or response.response.get("outcome") != "acknowledged"
            or response.response.get("request_digest") != request.digest()
        ):
            raise ValueError()
    except ValueError:
        raise HTTPException(409, "original Google response evidence changed") from None
    return OriginalOperationCompletionView(
        status="completed",
        purpose=document.capture.purpose,
        profile=document.capture.profile,
        commitment=document.digest(),
    )

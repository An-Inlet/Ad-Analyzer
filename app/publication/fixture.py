"""Only registered compiler/transport: deterministic, local and unable to open sockets."""

from datetime import datetime
from uuid import uuid4

from app.publication.contracts import (
    BoundRequest,
    FixtureOperation,
    PublicationReviewV2,
    PublicationScope,
    PublishPlan,
    PublishReceipt,
    PublishStep,
)


class FixtureCompiler:
    def compile(self, review: PublicationReviewV2) -> PublishPlan:
        source = review.source
        scope = PublicationScope(
            workspace_id=source.workspace_id,
            external_advertiser_id=review.external_advertiser_id,
            account=source.definition.account,
            connection_version=source.connection_version,
            mandate_id=source.definition.mandate_id,
            mandate_revision=source.definition.mandate_revision,
        )
        kinds = ["budget", "campaign", "group", "ad"]
        return PublishPlan(
            scope=scope,
            review=review,
            review_digest=review.digest(),
            exposure_micros=source.definition.budget_micros,
            steps=[
                PublishStep(
                    step_id=kind,
                    dependencies=[kinds[index - 1]] if index else [],
                    operation=FixtureOperation.model_validate(
                        {
                            "resource_kind": kind,
                            "name": source.definition.content.name,
                            "parent": {"step_id": kinds[index - 1]} if index else None,
                            "content_digest": review.digest(),
                        }
                    ),
                )
                for index, kind in enumerate(kinds)
            ],
        )


def compile_registered(compiler_id: str, review: PublicationReviewV2) -> PublishPlan:
    if compiler_id != "fixture_v1":
        raise ValueError("publication compiler unavailable")
    return FixtureCompiler().compile(review)


class FixturePublicationTransport:
    def __init__(self) -> None:
        self.resources: dict[str, PublishReceipt] = {}
        self.calls = 0
        self.timeout_after_apply = False
        self.timeout_before_apply = False
        self.no_proof = False

    def apply_once(self, request: BoundRequest, now: datetime) -> PublishReceipt:
        self.calls += 1
        if self.timeout_before_apply:
            raise TimeoutError("synthetic pre-effect timeout")
        key = request.digest()
        if key not in self.resources:
            self.resources[key] = PublishReceipt(
                scope=request.scope,
                plan_id=request.plan_id,
                step_id=request.step.step_id,
                fence=request.fence,
                request_digest=key,
                outcome="verified_effect",
                resource_id="fixture_" + uuid4().hex,
                status="PAUSED",
                observed_at=now,
            )
        if self.timeout_after_apply:
            raise TimeoutError("synthetic post-effect timeout")
        return self.resources[key]

    def reconcile(self, request: BoundRequest, now: datetime) -> PublishReceipt:
        if self.no_proof:
            outcome = "unknown"
        elif request.digest() in self.resources:
            return self.resources[request.digest()].model_copy(update={"observed_at": now})
        else:
            # An absent resource cannot prove a claimed worker will never submit.
            # Preserve its original fence until an effect is actually observed.
            outcome = "unknown"
        return PublishReceipt.model_validate(
            {
                "scope": request.scope.model_dump(),
                "plan_id": request.plan_id,
                "step_id": request.step.step_id,
                "fence": request.fence,
                "request_digest": request.digest(),
                "outcome": outcome,
                "observed_at": now,
            }
        )


def require_fixture(adapter: object) -> FixturePublicationTransport:
    if type(adapter) is not FixturePublicationTransport:
        raise ValueError("only exact offline fixture transport is available")
    return adapter


def get_publication_transport() -> None:
    # Deliberately no environment switch or live adapter construction in this package.
    return None

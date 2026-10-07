"""Concrete bounded native inventory then trusted admission and exact adapter readback."""

from collections import Counter
from collections.abc import Callable
from datetime import datetime
from time import monotonic
from typing import Literal

import httpx

from app.collectors.google_native_inventory import (
    GoogleAccountObservationRequestV2,
    GoogleInventoryRequest,
    GoogleNativeInventoryContext,
    GoogleNativeInventoryHTTP,
)
from app.collectors.meta_native_inventory import (
    MetaAccountObservationRequestV2,
    MetaInventoryRequest,
    MetaNativeInventoryContext,
    MetaNativeInventoryHTTP,
)
from app.executors.google_optimization import GoogleOptimizationTransport
from app.executors.meta_optimization import MetaOptimizationTransport
from app.production_runtime.optimization_catalog_contracts import (
    ExclusionReason,
    OwnedOptimizationAdmission,
    OwnedOptimizationCatalogRead,
)
from app.production_runtime.optimization_contracts import (
    OptimizationCatalogAdmissionReader,
    OwnedOptimizationCandidateV1,
    OwnedOptimizationInventoryRequestV1,
)
from app.publication.contracts import fingerprint
from app.publication.customer_optimization_contracts import TargetCatalog, TargetOption
from app.publication.execution_contracts import ExecutionAccount
from app.publication.optimization_contracts import OptimizationContext, OptimizationTarget


class OwnedOptimizationCatalogUnavailable(RuntimeError):
    """Sanitized failure, no partial catalog or response content."""


class _BoundedTransport(httpx.BaseTransport):
    def __init__(self, transport: httpx.BaseTransport, check: Callable[[], None]) -> None:
        self.transport, self.check = transport, check
        self.calls = self.bytes = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.check()
        self.calls += 1
        if self.calls > 1000:
            raise OwnedOptimizationCatalogUnavailable("optimization_catalog_capacity")
        response = self.transport.handle_request(request)
        body = bytearray()
        try:
            for chunk in [response.content] if response.is_stream_consumed else response.iter_raw():
                self.check()
                self.bytes += len(chunk)
                if self.bytes > 16_000_000 or len(body) + len(chunk) > 1_000_000:
                    raise OwnedOptimizationCatalogUnavailable("optimization_catalog_capacity")
                body.extend(chunk)
            self.check()
            return httpx.Response(
                response.status_code, headers=response.headers, content=bytes(body)
            )
        finally:
            response.close()

    def close(self) -> None:
        pass  # Enclosing request owns the shared transport.


class OwnedOptimizationCatalogHTTP:
    def __init__(
        self,
        context_reader: Callable[[ExecutionAccount], OptimizationContext],
        admission: OptimizationCatalogAdmissionReader,
        *,
        environment: Literal["contract_test", "live"],
        transport: httpx.BaseTransport,
        clock: Callable[[], datetime],
    ) -> None:
        self.context_reader, self.admission = context_reader, admission
        self.environment, self.transport, self.clock = environment, transport, clock

    def read(
        self, request: OwnedOptimizationInventoryRequestV1, now: datetime
    ) -> OwnedOptimizationCatalogRead:
        try:
            return self._read(
                OwnedOptimizationInventoryRequestV1.model_validate(request.model_dump()), now
            )
        except Exception:
            raise OwnedOptimizationCatalogUnavailable("optimization_catalog_unavailable") from None

    def _read(
        self, request: OwnedOptimizationInventoryRequestV1, now: datetime
    ) -> OwnedOptimizationCatalogRead:
        scope, money = request.request.scope, request.money
        if request.original_mandate and request.original_mandate.environment != self.environment:
            raise ValueError("environment")
        deadline = monotonic() + 60
        expiry: datetime | None = None

        def check() -> None:
            current = self.clock()
            if current < now or monotonic() >= deadline or (expiry and current >= expiry):
                raise ValueError("expired")

        def context() -> OptimizationContext:
            nonlocal expiry
            check()
            value = self.context_reader(scope)
            expiry = min(expiry, value.expires_at) if expiry else value.expires_at
            check()
            if value.scope != scope:
                raise ValueError("scope")
            return value

        def context_values() -> dict[str, object]:
            value = context()
            return {key: getattr(value, key) for key in OptimizationContext.model_fields}

        wire = _BoundedTransport(self.transport, check)
        args = dict(
            account=scope,
            currency=money.currency,
            time_zone=money.account_timezone,
            period_start=money.period_start,
            period_end=money.period_end,
        )
        targets: list[OptimizationTarget] = []
        owners: dict[str, str] = {}
        topology: dict[str, set[tuple[str, str]]] = {}
        excluded: Counter[ExclusionReason] = Counter()
        google = GoogleOptimizationTransport(transport=wire)
        meta = MetaOptimizationTransport(transport=wire)
        if scope.account.platform == "google_ads":

            def google_context(
                req: GoogleInventoryRequest, at: datetime
            ) -> GoogleNativeInventoryContext:
                return GoogleNativeInventoryContext(
                    **context_values(), request_digest=req.digest()
                )

            inventory = GoogleNativeInventoryHTTP(google_context, transport=wire, clock=self.clock)(
                GoogleAccountObservationRequestV2(**args), now
            )
            if (
                not inventory.advertising_inventory_read_complete
                or not inventory.billing_inventory_read_complete
            ):
                raise ValueError("incomplete")
            if len(inventory.campaigns) > 50:
                raise ValueError("capacity")
            budgets = {b.resource_name: b for b in inventory.campaign_budgets}
            for campaign in inventory.campaigns:
                budget = budgets.get(campaign.budget_resource)
                budget_campaigns = [
                    c
                    for c in inventory.campaigns
                    if c.budget_resource == campaign.budget_resource and c.status != "REMOVED"
                ]
                if (
                    campaign.status not in {"ENABLED", "PAUSED"}
                    or budget is None
                    or budget.explicitly_shared
                    or budget.reference_count != 1
                    or len(budget_campaigns) != 1
                    or budget.status != "ENABLED"
                    or budget.period != "DAILY"
                    or budget.type != "STANDARD"
                    or campaign.channel != "SEARCH"
                    or campaign.bidding_strategy != "MANUAL_CPC"
                ):
                    excluded["unsupported_owner"] += 1
                    continue
                identity = campaign.resource_name.rsplit("/", 1)[1]
                owners[identity] = campaign.budget_resource
                topology[identity] = {("campaign", identity)}
                targets.append(
                    OptimizationTarget(kind="campaign", external_id=identity, campaign_id=identity)
                )
            inventory_digest = inventory.digest()
            inventory_expiry = inventory.expires_at
        else:

            def meta_context(req: MetaInventoryRequest, at: datetime) -> MetaNativeInventoryContext:
                return MetaNativeInventoryContext(
                    **context_values(), request_digest=req.digest()
                )

            native = MetaNativeInventoryHTTP(meta_context, transport=wire, clock=self.clock)(
                MetaAccountObservationRequestV2(**args), now
            )
            if not native.advertising_inventory_read_complete or len(native.campaigns) > 50:
                raise ValueError("incomplete or capacity")
            for meta_campaign in native.campaigns:
                if (
                    meta_campaign.configured_status not in {"ACTIVE", "PAUSED"}
                    or meta_campaign.budget_schedule_enabled is not False
                    or meta_campaign.budget_sharing_enabled is not False
                    or meta_campaign.budget_rebalance_enabled is not False
                    or sum(
                        v is not None and v > 0
                        for v in [
                            meta_campaign.daily_budget_native,
                            meta_campaign.lifetime_budget_native,
                        ]
                    )
                    != 1
                ):
                    excluded["unsupported_owner"] += 1
                    continue
                topology[meta_campaign.id] = {("campaign", meta_campaign.id)} | {
                    ("adset", child.id)
                    for child in native.adsets
                    if child.campaign_id == meta_campaign.id
                }
                targets.append(
                    OptimizationTarget(
                        kind="campaign", external_id=meta_campaign.id, campaign_id=meta_campaign.id
                    )
                )
            inventory_digest = fingerprint(
                "inlet.meta-native-inventory.v1", native.model_dump(mode="json")
            )
            inventory_expiry = native.expires_at
        expiry = min(expiry, inventory_expiry) if expiry else inventory_expiry
        options: list[TargetOption] = []
        admitted: list[OwnedOptimizationAdmission] = []
        for target in targets:
            token = context()
            if scope.account.platform == "google_ads":
                label_row = google.single(
                    token,
                    "SELECT campaign.id, campaign.name FROM campaign "
                    f"WHERE campaign.id = {target.external_id}",
                    "campaign",
                )
                identity = str(label_row.get("id"))
            else:
                label_row = meta.node(target.external_id, "id,account_id,name", token)
                identity = str(label_row.get("id"))
                if label_row.get("account_id") != scope.external_advertiser_id:
                    raise ValueError("label account")
            context()
            if identity != target.external_id:
                raise ValueError("label target")
            label = label_row.get("name")
            if not isinstance(label, str) or not 1 <= len(label.strip()) <= 160:
                excluded["label_unavailable"] += 1
                continue
            candidate = OwnedOptimizationCandidateV1(
                request_digest=request.digest(),
                label=label,
                parent_label=label,
                target=target,
                inventory_digest=inventory_digest,
                observed_at=self.clock(),
                expires_at=expiry,
            )
            qualification = self.admission(request, candidate, self.clock())
            context()
            if qualification is None:
                excluded["unqualified"] += 1
                continue
            if (
                qualification.environment != self.environment
                or qualification.scope != scope
                or qualification.target != target
                or qualification.money != money
                or qualification.unresolved
                or not qualification.observed_at <= self.clock() < qualification.expires_at
            ):
                raise ValueError("admission mismatch")
            expiry = min(expiry, qualification.expires_at)
            state = (google if scope.account.platform == "google_ads" else meta).read_current(
                scope,
                target,
                money,
                qualification.qualification_id,
                qualification.qualification_revision,
                context(),
                self.clock(),
            )
            context()
            if (
                state.scope != scope
                or state.target != target
                or state.money != money
                or state.qualification_id != qualification.qualification_id
                or state.qualification_revision != qualification.qualification_revision
            ):
                raise ValueError("state mismatch")
            if (
                {(t.kind, t.external_id) for t in state.budget_owner.affected_targets}
                != topology[target.external_id]
                or state.budget_owner.owner != target
                or (
                    state.budget_owner.provider == "google_ads"
                    and state.budget_owner.native_budget_resource != owners[target.external_id]
                )
            ):
                raise ValueError("topology changed")
            if not state.complete or state.unsupported_features:
                excluded["unsupported_state"] += 1
                continue
            option = TargetOption(label=label, parent_label=label, state=state)
            options.append(option)
            admitted.append(
                OwnedOptimizationAdmission(
                    option.identifier(request.request), candidate, qualification, state.digest()
                )
            )
        context()
        return OwnedOptimizationCatalogRead(
            TargetCatalog(
                request=request.request,
                observed_at=self.clock(),
                expires_at=expiry,
                options=options,
                complete=True,
            ),
            tuple(admitted),
            tuple(sorted(excluded.items())),
        )

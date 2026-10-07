from datetime import timedelta

import httpx
import pytest
from app.commerce.acquisition_contracts import NativeHandles, initial_checkpoint
from app.commerce.acquisition_step import execute_step
from app.commerce.independent import IndependentAcquirer
from app.commerce.independent_contracts import ScanUnavailable

from tests.test_acquisition_checkpoint_contracts import profile
from tests.test_independent_acquisition import Fixture


def test_real_http_steps_match_independent_refund_metric_without_old_order_payload() -> None:
    fixture = Fixture()
    limits = profile()
    state = initial_checkpoint(fixture.request, limits)
    handles = NativeHandles(
        order_ids=(),
        last_order_number="0",
        order_cursor=None,
        agreement_cursor=None,
        sale_cursor=None,
        agreement_id=None,
    )
    seen: set[tuple[str, str]] = set()
    while state.phase != "publish":
        before = len(fixture.seen)
        result = execute_step(
            fixture.request,
            state,
            handles,
            fixture.authority,
            limits,
            transport=httpx.MockTransport(fixture.handle),
            clock=lambda: fixture.now,
            started_at=fixture.now,
            deadline_at=fixture.now + timedelta(minutes=30),
        )
        assert len(fixture.seen) == before + 1
        assert not seen.intersection(result.seen)
        seen.update(result.seen)
        state, handles = result.checkpoint, result.handles
        assert "gid://" not in state.model_dump_json()
        assert "gid://shopify/Customer" not in handles.model_dump_json()
    assert state.sequence == 5
    assert handles.order_ids == ()
    independent = IndependentAcquirer(
        fixture.authority, transport=httpx.MockTransport(fixture.handle), clock=lambda: fixture.now
    ).acquire(fixture.request)
    assert state.committed[0].value_micros == independent.days[0].value_micros == -10_000_000
    assert state.committed[0].entry_count == independent.days[0].entry_count == 1
    assert independent.correction_state == "unresolved"


def test_expired_step_emits_no_http() -> None:
    fixture = Fixture()
    limits = profile()
    state = initial_checkpoint(fixture.request, limits)
    handles = NativeHandles(
        order_ids=(),
        last_order_number="0",
        order_cursor=None,
        agreement_cursor=None,
        sale_cursor=None,
        agreement_id=None,
    )
    with pytest.raises(ScanUnavailable, match="acquisition_expired"):
        execute_step(
            fixture.request,
            state,
            handles,
            fixture.authority,
            limits,
            transport=httpx.MockTransport(fixture.handle),
            clock=lambda: fixture.now,
            started_at=fixture.now,
            deadline_at=fixture.now,
        )
    assert fixture.seen == []


@pytest.mark.parametrize("mode", ["nested_sales", "order_pages", "tampered_handle"])
def test_persisted_phase_and_actual_nested_pagination(mode: str) -> None:
    import json

    from tests.test_independent_acquisition import order, page, sale

    fixture = Fixture()
    limits = profile()
    state = initial_checkpoint(fixture.request, limits)
    handles = NativeHandles(
        order_ids=(),
        last_order_number="0",
        order_cursor=None,
        agreement_cursor=None,
        sale_cursor=None,
        agreement_id=None,
    )
    original = fixture.handle
    if mode == "nested_sales":
        fixture.agreement["sales"] = page([sale()], "more")

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if mode == "order_pages" and "InletIndependentOrders" in body["query"]:
            if body["variables"]["after"] is None:
                fixture.orders, fixture.cursor = [order(1)], "next-order"
            else:
                assert body["variables"]["after"] == "next-order"
                fixture.orders, fixture.cursor = [order(2)], None
                fixture.parent = "gid://shopify/Order/2"
                fixture.agreement["id"] = "gid://shopify/RefundAgreement/2"
                fixture.agreement["sales"] = page([sale(2)])
        return original(request)

    while state.phase != "publish":
        if mode == "tampered_handle" and state.phase == "agreement_page":
            before = len(fixture.seen)
            with pytest.raises(ScanUnavailable, match="acquisition_checkpoint_invalid"):
                execute_step(
                    fixture.request,
                    state,
                    handles.model_copy(update={"order_ids": ("gid://shopify/Order/99",)}),
                    fixture.authority,
                    limits,
                    transport=httpx.MockTransport(handle),
                    clock=lambda: fixture.now,
                    started_at=fixture.now,
                    deadline_at=fixture.now + timedelta(minutes=30),
                )
            assert len(fixture.seen) == before
            return
        result = execute_step(
            fixture.request,
            state,
            handles,
            fixture.authority,
            limits,
            transport=httpx.MockTransport(handle),
            clock=lambda: fixture.now,
            started_at=fixture.now,
            deadline_at=fixture.now + timedelta(minutes=30),
        )
        # Round-trip exactly the durable JSON boundary between each independent request.
        state = type(result.checkpoint).model_validate_json(result.checkpoint.model_dump_json())
        handles = NativeHandles.model_validate_json(result.handles.model_dump_json())
    assert state.committed[0].value_micros == -20_000_000
    assert state.sales_enumerated == 2


def test_failed_pre_io_validation_closes_owned_transport_once() -> None:
    fixture = Fixture()
    limits = profile()

    class Transport(httpx.MockTransport):
        closed = 0

        def close(self) -> None:
            self.closed += 1

    transport = Transport(fixture.handle)
    with pytest.raises(ScanUnavailable, match="acquisition_expired"):
        execute_step(
            fixture.request,
            initial_checkpoint(fixture.request, limits),
            NativeHandles(
                order_ids=(),
                last_order_number="0",
                order_cursor=None,
                agreement_cursor=None,
                sale_cursor=None,
                agreement_id=None,
            ),
            fixture.authority,
            limits,
            transport=transport,
            clock=lambda: fixture.now,
            started_at=fixture.now,
            deadline_at=fixture.now,
        )
    assert not fixture.seen and transport.closed == 1

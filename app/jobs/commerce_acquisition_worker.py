"""Dedicated bounded acquisition runner; disabled mode performs local cleanup only."""

from collections.abc import Callable
from threading import Event

from sqlalchemy import Engine

from app.commerce import acquisition_runtime as runtime
from app.commerce.acquisition_worker import cleanup, run_tick
from app.commerce.independent_contracts import ScanUnavailable
from app.customers.identity import IdentityProvider, get_identity_provider
from app.database.session import engine
from app.settings import Settings, settings


def tick(
    database: Engine,
    configuration: Settings,
    identity_factory: Callable[[], IdentityProvider] = get_identity_provider,
    *,
    stop_requested: Callable[[], bool] = lambda: False,
) -> float:
    cleanup(database, clock=runtime.utcnow)
    profile = runtime.load_profile(configuration)
    if profile is None or not runtime.enabled(database, configuration):
        return 30.0  # Local cleanup cadence, not an acquisition or financial policy.
    run_tick(
        database,
        configuration,
        identity_factory(),
        profile,
        lambda: runtime.acquisition_transport(configuration),
        clock=runtime.utcnow,
        stop_requested=stop_requested,
    )
    return float(profile.poll_interval_seconds)


def main() -> None:
    stopped = Event()
    try:
        while not stopped.is_set():
            try:
                delay = tick(engine, settings, stop_requested=stopped.is_set)
            except ScanUnavailable:
                delay = 30.0  # Missing configuration still leaves cleanup reachable.
            stopped.wait(delay)
    except KeyboardInterrupt:
        stopped.set()


if __name__ == "__main__":
    main()

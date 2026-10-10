"""Closed archive-source gate before current privacy requests."""

from pathlib import Path

from sqlalchemy import Engine

from tests.archive_financial_social_retained_fixture import retained_archive_source
from tests.test_customer_identity import customer_engine as customer_engine


def test_exact_archive_source(customer_engine: Engine, tmp_path: Path) -> None:
    with retained_archive_source(customer_engine, tmp_path / "archive-original") as (_, ids):
        assert ids.brand_a.provider == "meta_ads" and ids.brand_b.provider == "google_ads"

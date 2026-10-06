from datetime import timedelta

import pytest
from app.publication.execution_contracts import ExecutionAccount
from app.publication.social_catalog import (
    MetaCatalogOption,
    SocialCatalog,
    SocialCatalogRequest,
    TikTokCatalogOption,
)

from tests.test_provider_publication_contracts import NOW
from tests.test_social_publication_http import reviewed, tiktok_reviewed


def request(tiktok: bool = False) -> SocialCatalogRequest:
    review = tiktok_reviewed() if tiktok else reviewed()
    source = review.source
    return SocialCatalogRequest.model_validate(
        dict(
            account=ExecutionAccount.from_publication(review.scope),
            draft_id=source.draft_id,
            draft_revision=source.revision,
            source_digest=source.fingerprint(),
            countries=source.definition.content.audience.countries,
            languages=source.definition.content.audience.languages,
            content_kind=source.definition.content.kind,
        )
    )


def catalog(tiktok: bool = False) -> SocialCatalog:
    option = (
        TikTokCatalogOption(
            label="Store / Purchase", profile_digest="a" * 64, identity_id="identity", pixel_id="42"
        )
        if tiktok
        else MetaCatalogOption(
            label="Store / Purchase", profile_digest="a" * 64, page_id="41", pixel_id="42"
        )
    )
    return SocialCatalog(
        request=request(tiktok),
        observed_at=NOW,
        expires_at=NOW + timedelta(seconds=60),
        currency="USD",
        account_timezone="UTC",
        options=[option],
        unavailable_reasons=[],
        qualification_blockers=[
            "tiktok_native_catalog_parser_unverified"
            if tiktok
            else "native_configuration_unqualified"
        ],
        discovery_evidence="tiktok_decoded_contract_only" if tiktok else "meta_account_edges",
    )


@pytest.mark.parametrize("tiktok", [False, True])
def test_option_changes_with_source_generation_and_profile(tiktok: bool) -> None:
    c = catalog(tiktok)
    original = c.options[0].identifier(c.request)
    changed = c.request.model_copy(deep=True)
    changed.account.connection_version += ":next"
    assert c.options[0].identifier(changed) != original
    changed = c.request.model_copy(update={"source_digest": "b" * 64})
    assert c.options[0].identifier(changed) != original
    assert (
        c.options[0].model_copy(update={"profile_digest": "b" * 64}).identifier(c.request)
        != original
    )
    assert (
        c.model_copy(update={"observed_at": NOW + timedelta(seconds=1)})
        .options[0]
        .identifier(c.request)
        == original
    )


@pytest.mark.parametrize("change", ["expiry", "duplicate", "foreign", "timezone", "tiktok_parser"])
def test_catalog_fail_closed(change: str) -> None:
    c = catalog(change == "tiktok_parser")
    data = c.model_dump()
    if change == "expiry":
        data["expires_at"] = NOW + timedelta(minutes=6)
    elif change == "duplicate":
        data["options"] *= 2
    elif change == "foreign":
        data["request"]["account"]["account"]["platform"] = "google_ads"
    elif change == "timezone":
        data["account_timezone"] = "not-a-zone"
    else:
        data["qualification_blockers"] = ["unqualified"]
    with pytest.raises((ValueError, KeyError)):
        SocialCatalog.model_validate(data)

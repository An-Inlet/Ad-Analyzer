"""Canonical values captured from unchanged a08db1b before approval refs existed."""

from app.publication.google_compiler import compile_google
from app.publication.social_compiler import compile_social

from tests.test_provider_publication_contracts import review
from tests.test_social_publication_contracts import meta_review


def test_legacy_exact_hashes_and_explicit_nulls_are_preserved() -> None:
    social, google = meta_review(), review()
    assert social.digest() == "166f9a4bb254b37ce1f12aa42baf8db1d99a3ff46243ae475d08c44e0fdcf81d"
    assert compile_social(social).digest() == (
        "1d076e88d5a36f5a7bc59ecfffb59c6d4ebcb9cc5489eb3f4a3c8d20bbc0570e"
    )
    assert google.digest() == "33a8d693f769d17b62d038213b74b6a994454b54a3b679759d33720b887d48ce"
    assert compile_google(google).digest() == (
        "2532e599c75b353661d4c8298f72c90d083e091720d5f33acbf40ee08c25cb95"
    )
    raw = social.model_dump(mode="json")
    assert "configuration_review" not in raw
    assert "dsa_beneficiary" in raw["configuration"]
    assert raw["configuration"]["dsa_beneficiary"] is None
    assert raw["configuration"]["dsa_payor"] is None

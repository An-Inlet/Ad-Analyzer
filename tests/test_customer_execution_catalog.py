from datetime import timedelta

import pytest
from app.publication.customer_catalog import (
    GoogleCatalog,
    GoogleCatalogOption,
    GoogleCatalogRequest,
)
from app.publication.execution_contracts import ExecutionAccount
from pydantic import ValidationError

from tests.test_commerce_measurement import NOW
from tests.test_provider_publication_contracts import review


def catalog() -> GoogleCatalog:
    source = review()
    request = GoogleCatalogRequest(
        account=ExecutionAccount.from_publication(source.scope),
        draft_id=source.source.draft_id,
        draft_revision=source.source.revision,
        source_digest=source.source_digest,
        countries=source.source.definition.content.audience.countries,
        languages=source.source.definition.content.audience.languages,
    )
    fields = source.configuration
    return GoogleCatalog(
        request=request,
        observed_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        options=[
            GoogleCatalogOption(
                label="Store Purchases",
                custom_conversion_goal=fields.custom_conversion_goal,
                conversion_actions=fields.conversion_actions,
                country_targets=fields.country_targets,
                language_targets=fields.language_targets,
            )
        ],
        unavailable_reasons=[],
    )


def test_catalog_selection_changes_with_scope_source_or_actual_option() -> None:
    original = catalog()
    selected = original.options[0].identifier(original.request)
    assert selected == catalog().options[0].identifier(original.request)
    changed = original.request.model_copy(
        update={"draft_revision": original.request.draft_revision + 1}
    )
    assert selected != original.options[0].identifier(changed)
    changed_option = original.options[0].model_copy(update={"label": "Different Purchases"})
    assert selected != changed_option.identifier(original.request)


@pytest.mark.parametrize("mutation", ["expiry", "foreign", "duplicate", "audience"])
def test_catalog_fails_closed(mutation: str) -> None:
    raw = catalog().model_dump()
    if mutation == "expiry":
        raw["expires_at"] = NOW + timedelta(minutes=6)
    elif mutation == "foreign":
        raw["options"][0]["custom_conversion_goal"] = (
            "customers/9999999999/customConversionGoals/42"
        )
    elif mutation == "duplicate":
        raw["options"] *= 2
    else:
        raw["options"][0]["country_targets"] = {}
    with pytest.raises(ValidationError):
        GoogleCatalog.model_validate(raw)

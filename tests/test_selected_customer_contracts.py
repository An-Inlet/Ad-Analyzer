import pytest
from app.google_connections.selected_customer import AccountIntent, SelectionIntent, SelectionView
from pydantic import ValidationError


@pytest.mark.parametrize("value", [True, "1", 0, -1, 2**31])
def test_account_input_is_strict_positive_bounded(value: object) -> None:
    with pytest.raises(ValidationError):
        AccountIntent.model_validate({"account_id": value})


def test_cas_pair_and_public_scope_reject_untrusted_fields() -> None:
    raw = dict(
        account_id=1,
        option_id="a" * 64,
        expected_selection_id="b" * 32,
        expected_selection_digest=None,
    )
    with pytest.raises(ValidationError):
        SelectionIntent.model_validate(raw)
    raw.update(expected_selection_digest="c" * 64, scope={"account_id": 1})
    with pytest.raises(ValidationError):
        SelectionIntent.model_validate(raw)


def test_unavailable_is_not_a_current_selection() -> None:
    with pytest.raises(ValidationError):
        SelectionView(account_id=1, state="selected")
    with pytest.raises(ValidationError):
        SelectionView(
            account_id=1,
            state="refresh_required",
            selection_id="a" * 32,
            selection_digest="b" * 64,
            label="Not current",
        )

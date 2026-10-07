import pytest
from app.sources.models import SourceConnection
from app.sources.service import view


@pytest.mark.parametrize("provider", ["tiktok_ads", "klaviyo", "hubspot", "omnisend"])
def test_terminal_status_has_action_without_private_provider_message(provider: str) -> None:
    for state, label, action in [
        (
            "provider_error",
            "Provider Request Rejected",
            "Review provider access or configuration, then reconnect",
        ),
        ("reconnect_required", "Reconnection Required", "Reconnect this account to resume imports"),
    ]:
        row = SourceConnection(provider=provider, status=state)
        result = view(row)
        assert result["status_label"] == label
        assert result["next_action"] == action
        assert result["live_verified"] is False
    result = view(SourceConnection(provider=provider, status="connected"))
    assert "status_label" not in result and "next_action" not in result

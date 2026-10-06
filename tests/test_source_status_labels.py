from app.sources.models import SourceConnection
from app.sources.service import view


def test_tiktok_terminal_status_has_action_without_private_provider_message() -> None:
    for state, label, action in [
        (
            "provider_error",
            "Provider Request Rejected",
            "Review provider access or configuration, then reconnect",
        ),
        ("reconnect_required", "Reconnection Required", "Reconnect this account to resume imports"),
    ]:
        row = SourceConnection(provider="tiktok_ads", status=state)
        result = view(row)
        assert result["status_label"] == label
        assert result["next_action"] == action
        assert result["live_verified"] is False
    for provider, status in [("hubspot", "provider_error"), ("tiktok_ads", "connected")]:
        result = view(SourceConnection(provider=provider, status=status))
        assert "status_label" not in result and "next_action" not in result

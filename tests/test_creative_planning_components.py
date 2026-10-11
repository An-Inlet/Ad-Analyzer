"""Private v5 editor components; actual authenticated TLS journeys live separately."""

from pathlib import Path

import pytest

from tests.test_plan_target_picker import (
    test_target_picker_exact_choices_revocation_expiry_and_bounds as run_component,
)


def test_private_creative_editor_and_owned_media_components(tmp_path: Path) -> None:
    run_component(tmp_path, "plan_creative_inputs_dom")


def test_owned_image_csp_adds_only_self_and_blob(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.portal import auth

    monkeypatch.setattr(auth, "browser_identity_config", lambda: auth.BrowserIdentityConfig())
    assert auth.customer_content_security_policy() == (
        "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
        "frame-src 'none'; img-src 'self' blob:; media-src 'self' blob:; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    )

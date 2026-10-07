import pytest
from app.settings import settings
from app.sources.security import SourceVault
from cryptography.fernet import Fernet
from fastapi import HTTPException
from pydantic import SecretStr


@pytest.mark.parametrize("global_key", [None, SecretStr(Fernet.generate_key().decode())])
def test_explicit_source_vault_configuration_is_independent(
    monkeypatch: pytest.MonkeyPatch, global_key: SecretStr | None
) -> None:
    configuration = settings.model_copy(
        update={"source_token_encryption_key": SecretStr(Fernet.generate_key().decode())}
    )
    payload = {"access_token": "offline-test-only"}
    encrypted = SourceVault(configuration).seal(12, "tiktok_ads", "connection", payload)
    monkeypatch.setattr(settings, "source_token_encryption_key", global_key)
    assert SourceVault(configuration).open(12, "tiktok_ads", "connection", encrypted) == payload
    with pytest.raises(HTTPException) as caught:
        SourceVault().open(12, "tiktok_ads", "connection", encrypted)
    assert caught.value.status_code == (503 if global_key is None else 409)
    with pytest.raises(HTTPException) as foreign:
        SourceVault(configuration).open(13, "tiktok_ads", "connection", encrypted)
    assert foreign.value.status_code == 409

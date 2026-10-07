import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from app.settings import settings


class SourceVault:
    def __init__(self) -> None:
        key = settings.source_token_encryption_key
        if key is None:
            raise HTTPException(503, "source encryption unavailable")
        try:
            self.cipher = Fernet(key.get_secret_value().encode())
        except ValueError:
            raise HTTPException(503, "source encryption unavailable") from None

    def seal(self, workspace: int, provider: str, context: str, data: dict[str, Any]) -> str:
        return self.cipher.encrypt(
            json.dumps([workspace, provider, context, data]).encode()
        ).decode()

    def open(self, workspace: int, provider: str, context: str, ciphertext: str) -> dict[str, Any]:
        try:
            value = json.loads(self.cipher.decrypt(ciphertext.encode()))
            if value[:3] != [workspace, provider, context] or not isinstance(value[3], dict):
                raise ValueError()
            return dict(value[3])
        except (InvalidToken, ValueError, TypeError, IndexError):
            raise HTTPException(409, "source reconnect required") from None

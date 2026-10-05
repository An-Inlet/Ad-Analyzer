import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from app.settings import settings


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class Vault:
    def __init__(self) -> None:
        key = settings.google_customer_encryption_key
        if key is None:
            raise HTTPException(503, "Google customer connection unavailable")
        try:
            self.cipher = Fernet(key.get_secret_value().encode())
        except ValueError:
            raise HTTPException(503, "Google customer connection unavailable") from None

    def seal(self, workspace_id: int, context: str, token: str) -> str:
        return self.cipher.encrypt(json.dumps([workspace_id, context, token]).encode()).decode()

    def open(self, workspace_id: int, context: str, ciphertext: str) -> str:
        try:
            data = json.loads(self.cipher.decrypt(ciphertext.encode()))
            if data[:2] != [workspace_id, context] or not isinstance(data[2], str):
                raise ValueError()
            return str(data[2])
        except (InvalidToken, ValueError, TypeError, IndexError):
            raise HTTPException(409, "Google reconnect required") from None

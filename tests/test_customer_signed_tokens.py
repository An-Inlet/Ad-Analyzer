"""Real Firebase/Google RSA verification with offline certificate and user transports."""

import json
import time
from collections.abc import Generator
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import firebase_admin  # type: ignore[import-untyped]
import pytest
from app.api.customer import router
from app.customers import identity
from app.customers.access import CSRF_COOKIE
from app.customers.identity import GoogleIdentityProvider, get_identity_provider
from app.database.session import get_db
from app.settings import settings
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from firebase_admin import auth
from google.auth import crypt, jwt
from google.auth.credentials import AnonymousCredentials
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_customer_identity import ORIGIN, PROJECT
from tests.test_customer_identity import customer_engine as customer_engine


@pytest.fixture()
def signed_provider(monkeypatch: pytest.MonkeyPatch) -> Generator[tuple[Any, Any], None, None]:
    monkeypatch.delenv("FIREBASE_AUTH_EMULATOR_HOST", raising=False)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    app = firebase_admin.initialize_app(
        AnonymousCredentials(),  # type: ignore[no-untyped-call]
        options={"projectId": PROJECT},
        name=uuid4().hex,
    )
    client = auth._get_client(app)
    # Only external transports are replaced. Real auth.verify_id_token, JWT decoding,
    # signature verification, claims validation and revocation checks still execute.
    client._token_verifier.request = lambda *args, **kwargs: SimpleNamespace(
        status=200, data=json.dumps({"fixture-key": public}).encode()
    )
    monkeypatch.setattr(
        client,
        "get_user",
        lambda uid: SimpleNamespace(
            disabled=False,
            email_verified=True,
            tokens_valid_after_timestamp=0,
        ),
    )
    monkeypatch.setattr(identity, "_admin_app", lambda project: app)
    signer = crypt.RSASigner.from_string(private, key_id="fixture-key")  # type: ignore[no-untyped-call]

    def token(subject: str = "alice", issued: int | None = None) -> str:
        now = int(time.time())
        encoded: bytes = jwt.encode(  # type: ignore[no-untyped-call]
            signer,
            {
                "iss": f"https://securetoken.google.com/{PROJECT}",
                "aud": PROJECT,
                "sub": subject,
                "email": "same@example.test",
                "email_verified": True,
                "auth_time": now - 10,
                "iat": issued or now - 1,
                "exp": now + 3600,
            },
        )
        return encoded.decode()

    try:
        yield app, token
    finally:
        firebase_admin.delete_app(app)


def test_equivalent_signature_spelling_cannot_reexchange_after_logout(
    signed_provider: tuple[Any, Any],
    customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    firebase_app, mint = signed_provider
    canonical = mint()
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    pad_bits = canonical[:-1] + alphabet[alphabet.index(canonical[-1]) + 1]
    variants = [canonical + "=", canonical + "==", pad_bits]
    # Establish the dependency's actual behavior, including a real RSA signature check.
    original = auth.verify_id_token(canonical, app=firebase_app, check_revoked=True)
    for altered in variants:
        assert auth.verify_id_token(altered, app=firebase_app, check_revoked=True) == original
    header, payload, signature = canonical.split(".")
    bad_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    with pytest.raises(HTTPException) as rejected:
        GoogleIdentityProvider(PROJECT).verify(f"{header}.{payload}.{bad_signature}")
    assert rejected.value.status_code == 401
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    app = FastAPI()
    app.include_router(router)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: GoogleIdentityProvider(PROJECT)
    with TestClient(app, base_url=ORIGIN) as browser:
        headers = {"Origin": ORIGIN, "X-Inlet-Request": "1"}

        def exchange(value: str) -> Any:
            return browser.post(
                "/api/customer/v1/session", json={"id_token": value}, headers=headers
            )

        first = exchange(canonical)
        assert first.status_code == 200
        alice = first.json()["user_id"]
        assert (
            browser.delete(
                "/api/customer/v1/session",
                headers={
                    "Origin": ORIGIN,
                    "X-CSRF-Token": browser.cookies[CSRF_COOKIE],
                },
            ).status_code
            == 204
        )
        for altered in [canonical, *variants]:
            assert exchange(altered).status_code == 401
        # A distinct freshly signed token and a different user remain valid.
        assert exchange(mint(issued=int(time.time()))).json()["user_id"] == alice
        other = exchange(mint("bob"))
        assert other.status_code == 200 and other.json()["user_id"] != alice

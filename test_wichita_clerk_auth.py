"""Clerk JWT auth for Wichita API."""

from __future__ import annotations

import importlib
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LIVE_AIS = FIXTURES / "live_ais"


def _fresh_api_server():
    import types

    api_maritime_aviation_stub = types.ModuleType("api_maritime_aviation")
    api_maritime_aviation_stub.add_maritime_aviation_routes = lambda app: app
    sys.modules["api_maritime_aviation"] = api_maritime_aviation_stub
    os.environ["WICHITA_CAPTURES_DIRS"] = str(FIXTURES)
    os.environ["WICHITA_AIS_FIXTURE_DIR"] = str(LIVE_AIS)
    os.environ["WICHITA_ADSB_FIXTURE_DIR"] = str(FIXTURES / "live_adsb")
    if "api_server" in sys.modules:
        return importlib.reload(sys.modules["api_server"])
    import api_server

    return api_server


def _make_test_jwks(tmp_path: Path):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    pub_numbers = public_key.public_numbers()
    from jwt.utils import base64url_encode

    def b64url_uint(val: int) -> str:
        length = (val.bit_length() + 7) // 8
        return base64url_encode(val.to_bytes(length, "big")).decode("ascii")

    kid = "test-key"
    jwks = {
        "keys": [
            {
                "use": "sig",
                "kty": "RSA",
                "kid": kid,
                "alg": "RS256",
                "n": b64url_uint(pub_numbers.n),
                "e": b64url_uint(pub_numbers.e),
            }
        ]
    }
    jwks_path = tmp_path / "jwks.json"
    jwks_path.write_text(json.dumps(jwks), encoding="utf-8")
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return kid, pem, jwks_path


@contextmanager
def _auth_required_on():
    os.environ["WICHITA_AUTH_REQUIRED"] = "true"
    try:
        yield
    finally:
        os.environ["WICHITA_AUTH_REQUIRED"] = "false"


def _sign(pem: bytes, kid: str, iss: str, azp: str, sub: str = "user_test") -> str:
    now = int(time.time())
    headers = {"kid": kid, "alg": "RS256"}
    payload = {
        "sub": sub,
        "iss": iss,
        "azp": azp,
        "iat": now,
        "nbf": now - 5,
        "exp": now + 3600,
    }
    return jwt.encode(payload, pem, algorithm="RS256", headers=headers)


def test_unauthenticated_api_returns_401(tmp_path):
    kid, pem, jwks_path = _make_test_jwks(tmp_path)
    os.environ["WICHITA_CLERK_JWKS_PATH"] = str(jwks_path)
    os.environ["WICHITA_CLERK_FRONTEND_API"] = "https://clerk.test.example"
    os.environ["WICHITA_CLERK_AUTHORIZED_PARTIES"] = "https://wichitawire.com"
    with _auth_required_on():
        mod = _fresh_api_server()
        client = TestClient(mod.app)
        assert client.get("/api/feed-health").status_code == 401
        assert client.get("/health").status_code == 200
        assert client.get("/dashboard/clerk-env.json").status_code == 200


def test_valid_test_jwt_passes(tmp_path):
    kid, pem, jwks_path = _make_test_jwks(tmp_path)
    iss = "https://clerk.test.example"
    azp = "https://wichitawire.com"
    os.environ["WICHITA_CLERK_JWKS_PATH"] = str(jwks_path)
    os.environ["WICHITA_CLERK_FRONTEND_API"] = iss
    os.environ["WICHITA_CLERK_AUTHORIZED_PARTIES"] = azp
    with _auth_required_on():
        mod = _fresh_api_server()
        client = TestClient(mod.app)
        token = _sign(pem, kid, iss, azp)
        res = client.get("/api/feed-health", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200


def test_wrong_iss_or_azp_fails(tmp_path):
    kid, pem, jwks_path = _make_test_jwks(tmp_path)
    iss = "https://clerk.test.example"
    azp = "https://wichitawire.com"
    os.environ["WICHITA_CLERK_JWKS_PATH"] = str(jwks_path)
    os.environ["WICHITA_CLERK_FRONTEND_API"] = iss
    os.environ["WICHITA_CLERK_AUTHORIZED_PARTIES"] = azp
    with _auth_required_on():
        mod = _fresh_api_server()
        client = TestClient(mod.app)
        bad_iss = _sign(pem, kid, "https://evil.example", azp)
        bad_azp = _sign(pem, kid, iss, "https://evil.example")
        assert client.get("/api/feed-health", headers={"Authorization": f"Bearer {bad_iss}"}).status_code == 401
        assert client.get("/api/feed-health", headers={"Authorization": f"Bearer {bad_azp}"}).status_code == 401

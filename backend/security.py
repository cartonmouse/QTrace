from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_text, digest_text = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        salt = _unb64(salt_text)
        expected = _unb64(digest_text)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str, secret: str, ttl_seconds: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user_id, "exp": int(time.time()) + ttl_seconds}
    unsigned = f"{_b64(json.dumps(header, separators=(',', ':')).encode())}.{_b64(json.dumps(payload, separators=(',', ':')).encode())}"
    signature = hmac.new(secret.encode("utf-8"), unsigned.encode("ascii"), hashlib.sha256).digest()
    return f"{unsigned}.{_b64(signature)}"


def decode_access_token(token: str, secret: str) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".", 2)
        unsigned = f"{encoded_header}.{encoded_payload}"
        expected = hmac.new(secret.encode("utf-8"), unsigned.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(_unb64(encoded_signature), expected):
            raise ValueError("invalid signature")
        payload = json.loads(_unb64(encoded_payload))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired token")
        if not payload.get("sub"):
            raise ValueError("missing subject")
        return payload
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid access token") from exc


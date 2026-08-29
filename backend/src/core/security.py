"""密码哈希与 opaque session token。使用 bcrypt，禁止 passlib。"""

from __future__ import annotations

import hashlib
import hmac
import secrets

import bcrypt

# bcrypt 只接受不超过 72 字节的口令；更长时先 SHA-256 再哈希。
_BCRYPT_MAX_BYTES = 72
_SESSION_TOKEN_BYTES = 16


def _secret_bytes(plain: str) -> bytes:
    encoded = plain.encode("utf-8")
    if len(encoded) > _BCRYPT_MAX_BYTES:
        return hashlib.sha256(encoded).digest()
    return encoded


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_secret_bytes(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(_secret_bytes(plain), hashed.encode("utf-8"))


def generate_session_token() -> str:
    """签发 opaque session 明文 token；只在登录响应中出现一次。"""
    return secrets.token_hex(_SESSION_TOKEN_BYTES)


def hash_session_token(raw_token: str, secret_key: str) -> str:
    """Bearer token 的 HMAC-SHA256 十六进制摘要，长度 64，对应 sessions.token_hash。"""
    return hmac.new(
        secret_key.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

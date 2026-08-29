"""账号注册与登录服务。注册不签发 session；登录签发 opaque session。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pycore.core import get_logger

from src.core.config import get_settings
from src.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from src.db.models import Account
from src.models.auth import AuthSessionResponse, UserPublic
from src.repositories.account import AccountRepository
from src.repositories.session import SessionRepository

logger = get_logger()

_ACCOUNT_TAKEN_MESSAGE = "该账号名已被占用"
_INVALID_CREDENTIALS_MESSAGE = "账号或密码不正确"


class AccountConflictError(Exception):
    """账号名已被占用。"""

    def __init__(self, message: str = _ACCOUNT_TAKEN_MESSAGE) -> None:
        self.message = message
        super().__init__(message)


class InvalidCredentialsError(Exception):
    """账号不存在或密码不正确。对外同一文案，不暴露账号是否存在。"""

    def __init__(self, message: str = _INVALID_CREDENTIALS_MESSAGE) -> None:
        self.message = message
        super().__init__(message)


class AuthService:
    def __init__(self, repo: AccountRepository, session_repo: SessionRepository) -> None:
        self.repo = repo
        self.session_repo = session_repo

    def to_public(self, account: Account) -> UserPublic:
        return UserPublic(
            id=account.id,
            account=account.account,
            display_name=account.display_name,
        )

    async def register(self, account: str, password: str) -> UserPublic:
        existing = await self.repo.get_by_account(account)
        if existing is not None:
            raise AccountConflictError(_ACCOUNT_TAKEN_MESSAGE)
        password_hash = hash_password(password)
        try:
            row = await self.repo.create(
                account=account,
                password_hash=password_hash,
                display_name=account,
            )
        except ValueError as exc:
            raise AccountConflictError(_ACCOUNT_TAKEN_MESSAGE) from exc
        logger.info("Account registered", account_id=row.id)
        return self.to_public(row)

    async def login(self, account: str, password: str) -> AuthSessionResponse:
        row = await self.repo.get_by_account(account)
        if row is None or not verify_password(password, row.password_hash):
            logger.info("Login rejected", reason="invalid_credentials")
            raise InvalidCredentialsError(_INVALID_CREDENTIALS_MESSAGE)
        settings = get_settings()
        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token, settings.secret_key)
        expires_at = datetime.now(UTC) + timedelta(hours=settings.session_expire_hours)
        await self.session_repo.create(
            account_id=row.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        logger.info("Login succeeded", account_id=row.id)
        return AuthSessionResponse(token=raw_token, user=self.to_public(row))

    async def logout(self, raw_token: str) -> None:
        settings = get_settings()
        token_hash = hash_session_token(raw_token.strip(), settings.secret_key)
        deleted = await self.session_repo.delete_by_token_hash(token_hash)
        logger.info("Session revoked", deleted=deleted)

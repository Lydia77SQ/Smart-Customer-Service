"""FastAPI 依赖注入。基于 pycore/api/deps.py 模板扩展。

认证为路由级 Depends，不注册全局 AuthMiddleware。
会话来自项目 `src.db.session.get_db`，不使用 pycore 模板默认库。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import NoReturn

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pycore.api.responses import error_response, paginated_response, success_response
from pycore.core import get_logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.security import hash_session_token
from src.db.models import Account, Session
from src.db.session import get_db
from src.services.auth import AccountConflictError, InvalidCredentialsError
from src.services.knowledge import (
    KnowledgeNotFoundError,
    KnowledgeToggleConflictError,
    KnowledgeValidationError,
)
from src.services.ticket import TicketConflictError, TicketNotFoundError, TicketValidationError

logger = get_logger()
security = HTTPBearer(auto_error=False)

_UNAUTHORIZED_MESSAGE = "未认证"

# 供测试与登录签发复用，实现位于 src.core.security。
__all__ = [
    "UnauthorizedError",
    "contract_error_response",
    "contract_paginated_response",
    "contract_success_response",
    "get_current_user",
    "hash_session_token",
    "register_auth_exception_handlers",
    "security",
]


class UnauthorizedError(Exception):
    """路由级认证失败，由异常处理器转为 401 统一信封。"""

    def __init__(self, message: str = _UNAUTHORIZED_MESSAGE) -> None:
        self.message = message


def contract_error_response(
    message: str,
    error_code: str,
    status_code: int,
    *,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """把 pycore error_response 映射为契约信封 {code, message, data}。"""
    api_resp, http_status = error_response(
        error=message,
        error_code=error_code,
        status_code=status_code,
    )
    return JSONResponse(
        status_code=http_status,
        content={
            "code": api_resp.error_code,
            "message": api_resp.error or message,
            "data": None,
        },
        headers=headers,
    )


def contract_success_response(data: object, message: str = "ok") -> JSONResponse:
    """把 pycore success_response 映射为契约信封 {code, message, data}。"""
    api_resp = success_response(data=data, message=message)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "code": 200,
            "message": api_resp.message or "ok",
            "data": api_resp.data,
        },
    )


def contract_paginated_response(
    items: list[object],
    *,
    page: int,
    page_size: int,
    total_items: int,
    message: str = "ok",
) -> JSONResponse:
    """把 pycore paginated_response 映射为契约 data.items/page/page_size/total_items。"""
    api_resp = paginated_response(
        data=items,
        page=page,
        page_size=page_size,
        total_items=total_items,
    )
    pagination = api_resp.pagination
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "code": 200,
            "message": message,
            "data": {
                "items": api_resp.data,
                "page": pagination.page if pagination is not None else page,
                "page_size": pagination.page_size if pagination is not None else page_size,
                "total_items": pagination.total_items if pagination is not None else total_items,
            },
        },
    )


def _unauthorized_response(message: str = _UNAUTHORIZED_MESSAGE) -> JSONResponse:
    return contract_error_response(
        message,
        "UNAUTHORIZED",
        status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
    )


def register_auth_exception_handlers(app: FastAPI) -> None:
    """把认证失败、冲突与参数校验转成 api-contracts 信封。"""

    @app.exception_handler(UnauthorizedError)
    async def handle_unauthorized(_request: Request, exc: UnauthorizedError) -> JSONResponse:
        return _unauthorized_response(exc.message)

    @app.exception_handler(InvalidCredentialsError)
    async def handle_invalid_credentials(
        _request: Request, exc: InvalidCredentialsError
    ) -> JSONResponse:
        return _unauthorized_response(exc.message)

    @app.exception_handler(AccountConflictError)
    async def handle_conflict(_request: Request, exc: AccountConflictError) -> JSONResponse:
        return contract_error_response(
            exc.message,
            "CONFLICT",
            status.HTTP_409_CONFLICT,
        )

    @app.exception_handler(KnowledgeValidationError)
    async def handle_knowledge_validation(
        _request: Request, exc: KnowledgeValidationError
    ) -> JSONResponse:
        return contract_error_response(
            exc.message,
            "VALIDATION_ERROR",
            status.HTTP_400_BAD_REQUEST,
        )

    @app.exception_handler(KnowledgeNotFoundError)
    async def handle_knowledge_not_found(
        _request: Request, exc: KnowledgeNotFoundError
    ) -> JSONResponse:
        return contract_error_response(
            exc.message,
            "NOT_FOUND",
            status.HTTP_404_NOT_FOUND,
        )

    @app.exception_handler(KnowledgeToggleConflictError)
    async def handle_knowledge_toggle_conflict(
        _request: Request, exc: KnowledgeToggleConflictError
    ) -> JSONResponse:
        return contract_error_response(
            exc.message,
            "CONFLICT",
            status.HTTP_409_CONFLICT,
        )

    @app.exception_handler(TicketValidationError)
    async def handle_ticket_validation(
        _request: Request, exc: TicketValidationError
    ) -> JSONResponse:
        return contract_error_response(
            exc.message,
            "VALIDATION_ERROR",
            status.HTTP_400_BAD_REQUEST,
        )

    @app.exception_handler(TicketNotFoundError)
    async def handle_ticket_not_found(
        _request: Request, exc: TicketNotFoundError
    ) -> JSONResponse:
        return contract_error_response(
            exc.message,
            "NOT_FOUND",
            status.HTTP_404_NOT_FOUND,
        )

    @app.exception_handler(TicketConflictError)
    async def handle_ticket_conflict(
        _request: Request, exc: TicketConflictError
    ) -> JSONResponse:
        return contract_error_response(
            exc.message,
            "CONFLICT",
            status.HTTP_409_CONFLICT,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return contract_error_response(
            "参数验证失败",
            "VALIDATION_ERROR",
            status.HTTP_400_BAD_REQUEST,
        )


def _reject(reason: str) -> NoReturn:
    logger.info("Authentication rejected", reason=reason)
    raise UnauthorizedError(_UNAUTHORIZED_MESSAGE)


def _is_expired(expires_at: datetime) -> bool:
    aware = expires_at if expires_at.tzinfo is not None else expires_at.replace(tzinfo=UTC)
    return aware <= datetime.now(UTC)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Account:
    """校验 opaque session Bearer token，返回当前账号。"""
    if credentials is None:
        _reject("missing_token")
    raw_token = credentials.credentials.strip()
    if not raw_token:
        _reject("missing_token")
    token_hash = hash_session_token(raw_token, get_settings().secret_key)
    result = await db.execute(
        select(Account, Session)
        .join(Session, Session.account_id == Account.id)
        .where(Session.token_hash == token_hash)
    )
    row = result.one_or_none()
    if row is None:
        _reject("invalid_token")

    account, login_session = row
    if _is_expired(login_session.expires_at):
        _reject("expired_token")
    return account

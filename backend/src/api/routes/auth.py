"""账号 / 登录状态资源路由。"""

from fastapi import Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from pycore.api import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import (
    contract_success_response,
    get_current_user,
    security,
)
from src.db.models import Account
from src.db.session import get_db
from src.models.auth import AuthLoginRequest, AuthRegisterRequest, UserPublic
from src.repositories.account import AccountRepository
from src.repositories.session import SessionRepository
from src.services.auth import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _auth_service(db: AsyncSession) -> AuthService:
    return AuthService(AccountRepository(db), SessionRepository(db))


@router.post("/register")
async def register_account(
    body: AuthRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """API-F002-01 本地账号注册。公开接口，不签发 session。"""
    user = await _auth_service(db).register(account=body.account, password=body.password)
    return contract_success_response(user.model_dump())


@router.post("/login")
async def login_account(
    body: AuthLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """API-F001-01 用户登录。每次成功新建 sessions 行。"""
    session = await _auth_service(db).login(account=body.account, password=body.password)
    return contract_success_response(session.model_dump())


@router.post("/logout")
async def logout_account(
    _current: Account = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """API-F001-02 退出登录。作废当前 Bearer token。"""
    raw_token = credentials.credentials if credentials is not None else ""
    await _auth_service(db).logout(raw_token)
    return contract_success_response(None)


@router.get("/me")
async def read_current_user(
    current: Account = Depends(get_current_user),
) -> JSONResponse:
    """API-F001-03 当前用户。供顶栏展示身份。"""
    user = UserPublic.model_validate(current)
    return contract_success_response(user.model_dump())

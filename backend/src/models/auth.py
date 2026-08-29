"""认证相关 Pydantic 模型，对齐 docs/api-contracts.md API-F001 / API-F002。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.core.config import get_settings

_settings = get_settings()


class AuthLoginRequest(BaseModel):
    """POST /api/auth/login 请求体。长度不按注册约束拦截，错误凭证统一 401。"""

    account: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthRegisterRequest(BaseModel):
    """POST /api/auth/register 请求体。"""

    account: str = Field(
        min_length=_settings.account_min_length,
        max_length=_settings.account_max_length,
    )
    password: str = Field(
        min_length=_settings.password_min_length,
        max_length=_settings.password_max_length,
    )


class UserPublic(BaseModel):
    """公开账号信息；不含密码与内部字段。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account: str
    display_name: str


class AuthSessionResponse(BaseModel):
    """POST /api/auth/login 成功 data。"""

    token: str
    user: UserPublic

"""路由级认证依赖：独立测试库，禁止 drop_all 运行时业务库。"""

from __future__ import annotations

import inspect
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.params import Depends as DependsClass
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.api.deps import (
    get_current_user,
    hash_session_token,
    register_auth_exception_handlers,
)
from src.core.config import get_settings
from src.db.models import Account, Session
from src.db.session import apply_schema, get_db, make_async_engine

RUNTIME_DB = Path(__file__).resolve().parents[1] / "data" / "service_robot.db"
VALID_TOKEN = "test-opaque-session-token"
INVALID_TOKEN = "not-a-valid-session-token"


@pytest.fixture
def isolated_db_file(tmp_path: Path) -> Path:
    db_file = tmp_path / "deps.db"
    assert db_file.resolve() != RUNTIME_DB.resolve()
    return db_file


@pytest.fixture
async def isolated_engine(isolated_db_file: Path) -> AsyncGenerator[AsyncEngine, None]:
    engine = make_async_engine(isolated_db_file)
    await apply_schema(engine)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def isolated_session_maker(isolated_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(isolated_engine, expire_on_commit=False)


@pytest.fixture
def probe_app(isolated_session_maker: async_sessionmaker[AsyncSession]) -> FastAPI:
    app = FastAPI()
    register_auth_exception_handlers(app)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with isolated_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    @app.get("/protected")
    async def protected_probe(user: Account = Depends(get_current_user)) -> dict[str, object]:
        return {
            "id": user.id,
            "account": user.account,
            "display_name": user.display_name,
        }

    return app


@pytest.fixture
async def client(probe_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=probe_app),
        base_url="http://test",
        trust_env=False,
    ) as ac:
        yield ac


async def _insert_login_session(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    raw_token: str,
    expires_at: datetime,
    account: str = "wang.li",
    display_name: str = "王丽",
) -> Account:
    async with session_maker() as db:
        user = Account(
            account=account,
            password_hash="unused-for-deps-tests",
            display_name=display_name,
        )
        db.add(user)
        await db.flush()
        db.add(
            Session(
                account_id=user.id,
                token_hash=hash_session_token(raw_token, get_settings().secret_key),
                expires_at=expires_at,
            )
        )
        await db.commit()
        await db.refresh(user)
        return user


def _assert_unauthorized_envelope(payload: object) -> None:
    assert isinstance(payload, dict)
    assert payload["code"] == "UNAUTHORIZED"
    assert payload["message"] == "未认证"
    assert payload["data"] is None


def test_get_current_user_binds_project_get_db() -> None:
    param = inspect.signature(get_current_user).parameters["db"]
    assert isinstance(param.default, DependsClass)
    assert param.default.dependency is get_db


def test_deps_source_does_not_use_pycore_session() -> None:
    from src.api import deps as deps_module

    text = Path(deps_module.__file__).read_text(encoding="utf-8")
    assert "from src.db.session import get_db" in text
    assert "pycore.integrations.db.session" not in text


def test_app_has_no_auth_middleware() -> None:
    from src.main import app

    names = [middleware.cls.__name__ for middleware in app.user_middleware]
    assert all("Auth" not in name for name in names)


async def test_missing_authorization_returns_401(client: AsyncClient) -> None:
    response = await client.get("/protected")
    assert response.status_code == 401
    _assert_unauthorized_envelope(response.json())


async def test_invalid_token_returns_401(
    client: AsyncClient, isolated_session_maker: async_sessionmaker[AsyncSession]
) -> None:
    await _insert_login_session(
        isolated_session_maker,
        raw_token=VALID_TOKEN,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    response = await client.get(
        "/protected",
        headers={"Authorization": f"Bearer {INVALID_TOKEN}"},
    )
    assert response.status_code == 401
    _assert_unauthorized_envelope(response.json())


async def test_valid_token_returns_current_user(
    client: AsyncClient, isolated_session_maker: async_sessionmaker[AsyncSession]
) -> None:
    user = await _insert_login_session(
        isolated_session_maker,
        raw_token=VALID_TOKEN,
        expires_at=datetime.now(UTC) + timedelta(hours=get_settings().session_expire_hours),
    )
    response = await client.get(
        "/protected",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user.id
    assert body["account"] == "wang.li"
    assert body["display_name"] == "王丽"


async def test_expired_token_returns_401(
    client: AsyncClient, isolated_session_maker: async_sessionmaker[AsyncSession]
) -> None:
    await _insert_login_session(
        isolated_session_maker,
        raw_token=VALID_TOKEN,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    response = await client.get(
        "/protected",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    )
    assert response.status_code == 401
    _assert_unauthorized_envelope(response.json())


async def test_deps_does_not_touch_runtime_db(
    isolated_db_file: Path, isolated_engine: AsyncEngine
) -> None:
    existed = RUNTIME_DB.is_file()
    runtime_mtime_before = RUNTIME_DB.stat().st_mtime_ns if existed else None
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()
    assert isolated_engine.url.database != str(RUNTIME_DB)
    if existed:
        assert RUNTIME_DB.stat().st_mtime_ns == runtime_mtime_before
    else:
        assert not RUNTIME_DB.is_file()

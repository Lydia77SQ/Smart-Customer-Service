"""F-001 用户登录：独立测试库，禁止 drop_all 运行时业务库。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.api.deps import hash_session_token, register_auth_exception_handlers
from src.api.routes.auth import router as auth_router
from src.core.config import get_settings
from src.core.security import hash_password
from src.db.models import Account, Session
from src.db.session import apply_schema, get_db, make_async_engine
from src.main import app as runtime_app

RUNTIME_DB = Path(__file__).resolve().parents[3] / "data" / "service_robot.db"
REGISTER_PATH = "/api/auth/register"
LOGIN_PATH = "/api/auth/login"
LOGOUT_PATH = "/api/auth/logout"
ME_PATH = "/api/auth/me"
ACCOUNT = "wang.li"
PASSWORD = "pass-word-6"
DISPLAY_NAME = "王丽"


@pytest.fixture
def isolated_db_file(tmp_path: Path) -> Path:
    db_file = tmp_path / "f001.db"
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
def login_app(isolated_session_maker: async_sessionmaker[AsyncSession]) -> FastAPI:
    app = FastAPI()
    register_auth_exception_handlers(app)
    app.include_router(auth_router.router)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with isolated_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture
async def client(login_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=login_app),
        base_url="http://test",
        trust_env=False,
    ) as ac:
        yield ac


async def _seed_account(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    account: str = ACCOUNT,
    password: str = PASSWORD,
    display_name: str = DISPLAY_NAME,
) -> Account:
    async with session_maker() as db:
        row = Account(
            account=account,
            password_hash=hash_password(password),
            display_name=display_name,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row


def _assert_unauthorized(payload: object, message: str) -> None:
    assert payload == {"code": "UNAUTHORIZED", "message": message, "data": None}


def test_login_routes_mounted_on_runtime_app() -> None:
    paths = {getattr(route, "path", None) for route in runtime_app.routes}
    assert LOGIN_PATH in paths
    assert LOGOUT_PATH in paths
    assert ME_PATH in paths


def test_login_does_not_touch_runtime_db(isolated_db_file: Path) -> None:
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()


async def test_login_success_issues_opaque_session(
    client: AsyncClient,
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = await _seed_account(isolated_session_maker)
    response = await client.post(
        LOGIN_PATH,
        json={"account": ACCOUNT, "password": PASSWORD},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["message"] == "ok"
    data = payload["data"]
    token = data["token"]
    assert isinstance(token, str) and len(token) >= 16
    assert data["user"] == {
        "id": user.id,
        "account": ACCOUNT,
        "display_name": DISPLAY_NAME,
    }
    assert "password" not in data
    assert "password_hash" not in data["user"]

    async with isolated_session_maker() as db:
        rows = (await db.execute(select(Session))).scalars().all()
        assert len(rows) == 1
        assert rows[0].account_id == user.id
        assert rows[0].token_hash != token
        assert rows[0].token_hash == hash_session_token(token, get_settings().secret_key)
        assert len(rows[0].token_hash) == 64


async def test_login_wrong_password_does_not_create_session(
    client: AsyncClient,
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_account(isolated_session_maker)
    response = await client.post(
        LOGIN_PATH,
        json={"account": ACCOUNT, "password": "wrong-password"},
    )
    assert response.status_code == 401
    _assert_unauthorized(response.json(), "账号或密码不正确")

    async with isolated_session_maker() as db:
        count = (await db.execute(select(func.count()).select_from(Session))).scalar_one()
        assert count == 0


async def test_login_unknown_account_same_message(
    client: AsyncClient,
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    response = await client.post(
        LOGIN_PATH,
        json={"account": "nobody.here", "password": PASSWORD},
    )
    assert response.status_code == 401
    _assert_unauthorized(response.json(), "账号或密码不正确")

    async with isolated_session_maker() as db:
        count = (await db.execute(select(func.count()).select_from(Session))).scalar_one()
        assert count == 0


async def test_login_then_me_and_logout(
    client: AsyncClient,
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = await _seed_account(isolated_session_maker)
    login = await client.post(
        LOGIN_PATH,
        json={"account": ACCOUNT, "password": PASSWORD},
    )
    token = login.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = await client.get(ME_PATH, headers=headers)
    assert me.status_code == 200
    assert me.json() == {
        "code": 200,
        "message": "ok",
        "data": {
            "id": user.id,
            "account": ACCOUNT,
            "display_name": DISPLAY_NAME,
        },
    }

    logout = await client.post(LOGOUT_PATH, headers=headers)
    assert logout.status_code == 200
    assert logout.json() == {"code": 200, "message": "ok", "data": None}

    async with isolated_session_maker() as db:
        count = (await db.execute(select(func.count()).select_from(Session))).scalar_one()
        assert count == 0

    me_again = await client.get(ME_PATH, headers=headers)
    assert me_again.status_code == 401
    _assert_unauthorized(me_again.json(), "未认证")

    logout_again = await client.post(LOGOUT_PATH, headers=headers)
    assert logout_again.status_code == 401
    _assert_unauthorized(logout_again.json(), "未认证")


async def test_me_and_logout_without_token(client: AsyncClient) -> None:
    me = await client.get(ME_PATH)
    assert me.status_code == 401
    _assert_unauthorized(me.json(), "未认证")

    logout = await client.post(LOGOUT_PATH)
    assert logout.status_code == 401
    _assert_unauthorized(logout.json(), "未认证")


async def test_second_login_keeps_previous_session(
    client: AsyncClient,
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_account(isolated_session_maker)
    first = await client.post(LOGIN_PATH, json={"account": ACCOUNT, "password": PASSWORD})
    second = await client.post(LOGIN_PATH, json={"account": ACCOUNT, "password": PASSWORD})
    token_a = first.json()["data"]["token"]
    token_b = second.json()["data"]["token"]
    assert token_a != token_b

    me_a = await client.get(ME_PATH, headers={"Authorization": f"Bearer {token_a}"})
    me_b = await client.get(ME_PATH, headers={"Authorization": f"Bearer {token_b}"})
    assert me_a.status_code == 200
    assert me_b.status_code == 200

    async with isolated_session_maker() as db:
        count = (await db.execute(select(func.count()).select_from(Session))).scalar_one()
        assert count == 2


async def test_expired_session_me_unauthorized(
    client: AsyncClient,
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = await _seed_account(isolated_session_maker)
    raw_token = "expired-opaque-token"
    async with isolated_session_maker() as db:
        db.add(
            Session(
                account_id=user.id,
                token_hash=hash_session_token(raw_token, get_settings().secret_key),
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        await db.commit()

    response = await client.get(ME_PATH, headers={"Authorization": f"Bearer {raw_token}"})
    assert response.status_code == 401
    _assert_unauthorized(response.json(), "未认证")


async def test_register_then_login_uses_account_display_name(
    client: AsyncClient,
) -> None:
    registered = await client.post(
        REGISTER_PATH,
        json={"account": "new.user", "password": PASSWORD},
    )
    assert registered.status_code == 200
    login = await client.post(
        LOGIN_PATH,
        json={"account": "new.user", "password": PASSWORD},
    )
    assert login.status_code == 200
    user = login.json()["data"]["user"]
    assert user["account"] == "new.user"
    assert user["display_name"] == "new.user"


@pytest.mark.parametrize(
    "body",
    [
        {"account": "", "password": PASSWORD},
        {"account": ACCOUNT, "password": ""},
        {"account": ACCOUNT},
        {"password": PASSWORD},
        {},
    ],
)
async def test_login_validation_error(client: AsyncClient, body: dict[str, str]) -> None:
    response = await client.post(LOGIN_PATH, json=body)
    assert response.status_code == 400
    assert response.json() == {
        "code": "VALIDATION_ERROR",
        "message": "参数验证失败",
        "data": None,
    }

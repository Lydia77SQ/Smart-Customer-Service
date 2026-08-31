"""E2E 夹具：独立测试库 + 独立上传目录 + 全资源路由。禁止操作运行时业务库。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.api.deps import register_auth_exception_handlers
from src.api.routes.auth import router as auth_router
from src.api.routes.knowledge_documents import router as knowledge_router
from src.api.routes.tickets import router as tickets_router
from src.core.config import get_settings
from src.db.session import apply_schema, get_db, make_async_engine

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DB = BACKEND_ROOT / "data" / "service_robot.db"
FRONTEND_SRC = PROJECT_ROOT / "frontend" / "src"

REGISTER_PATH = "/api/auth/register"
LOGIN_PATH = "/api/auth/login"
ME_PATH = "/api/auth/me"
UPLOAD_PATH = "/api/knowledge_documents"
LIST_KNOWLEDGE_PATH = "/api/knowledge_documents"
PATCH_KNOWLEDGE_PATH = "/api/knowledge_documents/{document_id}"
MESSAGES_PATH = "/api/tickets/messages"
MINE_PATH = "/api/tickets/mine"
DETAIL_PATH = "/api/tickets/{ticket_id}"
TRANSFER_PATH = "/api/tickets/{ticket_id}/transfer"
QUEUE_PATH = "/api/tickets/agent-queue"
ACCEPT_PATH = "/api/tickets/{ticket_id}/accept"
SUGGEST_PATH = "/api/tickets/{ticket_id}/suggestions"
REPLY_PATH = "/api/tickets/{ticket_id}/agent-replies"
CATEGORY_PATH = "/api/tickets/{ticket_id}/category"
CLOSE_PATH = "/api/tickets/{ticket_id}/close"

EMPLOYEE_ACCOUNT = "e2e.emp24"
AGENT_ACCOUNT = "e2e.agt24"
PASSWORD = "pass-word-6"
EMPLOYEE_QUESTION = "公司 VPN 连不上，提示认证失败。"
SYSTEM_ANSWER = "请使用邮箱验证码重置 VPN 口令。"
SUGGESTION_TEXT = "E2E-SUGGESTION-DO-NOT-LEAK-TO-EMPLOYEE"
AGENT_REPLY = "已为你重置了 VPN 口令，请用邮件里的新密码再试。"
TARGET_CATEGORY = "IT-网络"
VPN_MARKDOWN = (
    "# VPN 接入说明\n\n"
    "公司员工通过门户下载客户端后接入内网。\n\n"
    "## 忘记密码\n\n"
    "请使用邮箱验证码重置 VPN 口令。\n"
)
CLOSED_SEND_BODY = {"code": "CONFLICT", "message": "已完结，不能再发送", "data": None}


@pytest.fixture
def isolated_db_file(tmp_path: Path) -> Path:
    db_file = tmp_path / "e2e.db"
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
def isolated_upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(get_settings(), "upload_dir", str(upload_dir))
    return upload_dir


@pytest.fixture
def e2e_app(
    isolated_session_maker: async_sessionmaker[AsyncSession],
    isolated_upload_dir: Path,
) -> FastAPI:
    assert isolated_upload_dir.is_dir()
    app = FastAPI()
    register_auth_exception_handlers(app)
    app.include_router(auth_router.router)
    app.include_router(tickets_router.router)
    app.include_router(knowledge_router.router)

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
async def client(e2e_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=e2e_app),
        base_url="http://test",
        trust_env=False,
    ) as ac:
        yield ac

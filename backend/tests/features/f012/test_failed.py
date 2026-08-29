"""F-012 入库失败不得启用。禁止 drop_all 运行时业务库；不依赖真实百炼。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config import get_settings
from src.db.models import KnowledgeDocument
from src.services.embedding import EmbeddingError

LIST_PATH = "/api/knowledge_documents"
UPLOAD_PATH = "/api/knowledge_documents"
RUNTIME_DB = Path(__file__).resolve().parents[3] / "data" / "service_robot.db"
VPN_MARKDOWN = (
    "# VPN 接入说明\n\n"
    "公司员工通过门户下载客户端后接入内网。\n\n"
    "## 忘记密码\n\n"
    "请使用邮箱验证码重置 VPN 口令。\n"
)

pytestmark = pytest.mark.timeout(300)


def test_failed_path_does_not_touch_runtime_db(isolated_db_file: Path) -> None:
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()


async def test_missing_embedding_key_marks_failed_not_enabled(
    client: AsyncClient,
    auth_headers: dict[str, str],
    isolated_session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "dashscope_api_key", "")
    response = await client.post(
        UPLOAD_PATH,
        headers=auth_headers,
        files={"file": ("VPN接入说明.md", VPN_MARKDOWN.encode("utf-8"), "text/markdown")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert data["filename"] == "VPN接入说明.md"
    assert data["status"] == "failed"
    assert data["status"] != "enabled"

    listed = await client.get(LIST_PATH, headers=auth_headers)
    items = listed.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["status"] == "failed"
    assert items[0]["status"] != "enabled"

    async with isolated_session_maker() as db:
        document = (
            await db.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.id == data["id"])
            )
        ).scalar_one()
        assert document.status == "failed"
        enabled_count = (
            await db.execute(
                select(func.count())
                .select_from(KnowledgeDocument)
                .where(KnowledgeDocument.status == "enabled")
            )
        ).scalar_one()
        assert enabled_count == 0


async def test_embedding_error_marks_failed_not_enabled(
    client: AsyncClient,
    auth_headers: dict[str, str],
    isolated_session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(_self: object, _texts: list[str]) -> list[list[float]]:
        raise EmbeddingError("向量化调用失败")

    monkeypatch.setattr("src.services.knowledge.EmbeddingClient.embed_texts", boom)
    response = await client.post(
        UPLOAD_PATH,
        headers=auth_headers,
        files={"file": ("VPN接入说明.md", VPN_MARKDOWN.encode("utf-8"), "text/markdown")},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "failed"
    async with isolated_session_maker() as db:
        document = (
            await db.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.id == data["id"])
            )
        ).scalar_one()
        assert document.status == "failed"


@pytest.mark.skipif(
    not os.getenv("REAL_API_TEST"),
    reason="未设置 REAL_API_TEST，跳过真实百炼 Embedding 联调",
)
async def test_real_embedding_optional() -> None:
    """仅在显式授权时跑真实 Embedding；缺 Key 不得宣称联调通过。"""
    assert get_settings().dashscope_api_key.strip()
    pytest.skip("本任务环境百炼 Embedding 为 fallback，不在此宣称真实联调通过")

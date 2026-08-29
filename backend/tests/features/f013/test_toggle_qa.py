"""F-013 答疑影响约定：disabled 不参与后续检索。完整员工提问留给 T-016。"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config import get_settings
from src.repositories.knowledge import KnowledgeDocumentRepository
from src.services.knowledge import is_enabled_for_retrieval

pytestmark = pytest.mark.timeout(120)

LIST_PATH = "/api/knowledge_documents"
UPLOAD_PATH = "/api/knowledge_documents"
PATCH_PATH = "/api/knowledge_documents/{document_id}"
RUNTIME_DB = Path(__file__).resolve().parents[3] / "data" / "service_robot.db"

VPN_MARKDOWN = (
    "# VPN 接入说明\n\n"
    "公司员工通过门户下载客户端后接入内网。\n\n"
    "## 忘记密码\n\n"
    "请使用邮箱验证码重置 VPN 口令。\n"
)


def test_toggle_qa_does_not_touch_runtime_db(isolated_db_file: Path) -> None:
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()


def test_retrieval_helper_only_allows_enabled() -> None:
    assert is_enabled_for_retrieval("enabled") is True
    assert is_enabled_for_retrieval("disabled") is False
    assert is_enabled_for_retrieval("failed") is False
    assert is_enabled_for_retrieval("processing") is False


async def _fake_embed(_self: object, texts: list[str]) -> list[list[float]]:
    dim = get_settings().embedding_dimensions
    return [[0.01] * dim for _ in texts]


async def test_disabled_document_excluded_from_retrieval_ids(
    client: AsyncClient,
    auth_headers: dict[str, str],
    isolated_session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """停用后立即从检索候选中排除；不跑 T-016 答疑流水线。"""
    monkeypatch.setattr(
        "src.services.knowledge.EmbeddingClient.embed_texts",
        _fake_embed,
    )
    uploaded = await client.post(
        UPLOAD_PATH,
        headers=auth_headers,
        files={"file": ("VPN接入说明.md", VPN_MARKDOWN.encode("utf-8"), "text/markdown")},
    )
    document_id = int(uploaded.json()["data"]["id"])

    async with isolated_session_maker() as db:
        enabled_ids = await KnowledgeDocumentRepository(db).list_enabled_ids()
    assert document_id in enabled_ids

    disabled = await client.patch(
        PATCH_PATH.format(document_id=document_id),
        headers=auth_headers,
        json={"enabled": False},
    )
    assert disabled.json()["data"]["status"] == "disabled"
    listed = await client.get(LIST_PATH, headers=auth_headers)
    assert listed.json()["data"]["items"][0]["id"] == document_id
    assert listed.json()["data"]["items"][0]["status"] == "disabled"

    async with isolated_session_maker() as db:
        after_disable = await KnowledgeDocumentRepository(db).list_enabled_ids()
    assert document_id not in after_disable

    reenabled = await client.patch(
        PATCH_PATH.format(document_id=document_id),
        headers=auth_headers,
        json={"enabled": True},
    )
    assert reenabled.json()["data"]["status"] == "enabled"

    async with isolated_session_maker() as db:
        after_enable = await KnowledgeDocumentRepository(db).list_enabled_ids()
    assert document_id in after_enable

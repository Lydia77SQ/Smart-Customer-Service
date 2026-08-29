"""F-012 上传 Markdown：格式拒绝、入库成功默认启用。禁止 drop_all 运行时业务库。"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config import get_settings
from src.db.models import KnowledgeChunk, KnowledgeDocument, QaPair
from src.main import app as runtime_app
from src.services.knowledge import extract_qa_pairs, split_chunks

pytestmark = pytest.mark.timeout(300)

LIST_PATH = "/api/knowledge_documents"
UPLOAD_PATH = "/api/knowledge_documents"
RUNTIME_DB = Path(__file__).resolve().parents[3] / "data" / "service_robot.db"

VPN_MARKDOWN = (
    "# VPN 接入说明\n\n"
    "公司员工通过门户下载客户端后接入内网。\n\n"
    "## 忘记密码\n\n"
    "请使用邮箱验证码重置 VPN 口令。\n"
)


def test_knowledge_routes_mounted_on_runtime_app() -> None:
    paths = {getattr(route, "path", None) for route in runtime_app.routes}
    assert UPLOAD_PATH in paths


def test_upload_does_not_touch_runtime_db(isolated_db_file: Path) -> None:
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()


def test_split_chunks_uses_overlap() -> None:
    chunks = split_chunks("abcdefghij", chunk_size=4, overlap=1)
    assert chunks == ["abcd", "defg", "ghij"]


def test_extract_qa_from_headings() -> None:
    pairs = extract_qa_pairs(VPN_MARKDOWN, "VPN接入说明.md")
    assert pairs[0][0] == "VPN 接入说明"
    assert "门户下载客户端" in pairs[0][1]
    assert pairs[1] == ("忘记密码", "请使用邮箱验证码重置 VPN 口令。")


async def test_upload_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        UPLOAD_PATH,
        files={"file": ("note.md", b"# hi\n\nbody\n", "text/markdown")},
    )
    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHORIZED", "message": "未认证", "data": None}


async def test_list_requires_auth(client: AsyncClient) -> None:
    response = await client.get(LIST_PATH)
    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHORIZED", "message": "未认证", "data": None}


async def test_reject_non_markdown(
    client: AsyncClient,
    auth_headers: dict[str, str],
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    response = await client.post(
        UPLOAD_PATH,
        headers=auth_headers,
        files={"file": ("readme.txt", b"not markdown", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json() == {
        "code": "VALIDATION_ERROR",
        "message": "仅支持 Markdown",
        "data": None,
    }
    listed = await client.get(LIST_PATH, headers=auth_headers)
    assert listed.status_code == 200
    data = listed.json()["data"]
    assert data["total_items"] == 0
    assert data["items"] == []
    async with isolated_session_maker() as db:
        count = (
            await db.execute(select(func.count()).select_from(KnowledgeDocument))
        ).scalar_one()
        assert count == 0


async def test_reject_empty_markdown(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        UPLOAD_PATH,
        headers=auth_headers,
        files={"file": ("empty.md", b"   \n", "text/markdown")},
    )
    assert response.status_code == 400
    assert response.json() == {
        "code": "VALIDATION_ERROR",
        "message": "参数验证失败",
        "data": None,
    }


async def _fake_embed(_self: object, texts: list[str]) -> list[list[float]]:
    dim = get_settings().embedding_dimensions
    return [[0.01] * dim for _ in texts]


async def test_upload_markdown_enabled_with_chunks_and_qa(
    client: AsyncClient,
    auth_headers: dict[str, str],
    isolated_session_maker: async_sessionmaker[AsyncSession],
    isolated_upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.services.knowledge.EmbeddingClient.embed_texts",
        _fake_embed,
    )
    response = await client.post(
        UPLOAD_PATH,
        headers=auth_headers,
        files={"file": ("VPN接入说明.md", VPN_MARKDOWN.encode("utf-8"), "text/markdown")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["message"] == "ok"
    data = payload["data"]
    assert data["filename"] == "VPN接入说明.md"
    assert data["status"] == "enabled"
    assert isinstance(data["id"], int)
    assert data["updated_at"].endswith("Z")
    assert "storage_path" not in data

    listed = await client.get(LIST_PATH, headers=auth_headers)
    assert listed.status_code == 200
    page = listed.json()["data"]
    assert page["page"] == 1
    assert page["page_size"] == get_settings().knowledge_list_page_size
    assert page["total_items"] == 1
    assert page["items"][0]["id"] == data["id"]
    assert page["items"][0]["status"] == "enabled"
    assert page["items"][0]["filename"] == "VPN接入说明.md"

    stored = isolated_upload_dir / f"{data['id']}.md"
    assert stored.is_file()
    assert stored.read_text(encoding="utf-8") == VPN_MARKDOWN

    async with isolated_session_maker() as db:
        document = (
            await db.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.id == data["id"])
            )
        ).scalar_one()
        assert document.status == "enabled"
        chunks = (
            await db.execute(
                select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)
            )
        ).scalars().all()
        assert len(chunks) >= 1
        assert all(chunk.embedding is not None for chunk in chunks)
        pairs = (
            await db.execute(select(QaPair).where(QaPair.document_id == document.id))
        ).scalars().all()
        assert len(pairs) >= 1
        assert all(pair.embedding is not None for pair in pairs)
        fts_count = (
            await db.execute(text("SELECT COUNT(*) FROM knowledge_chunks_fts"))
        ).scalar_one()
        assert int(fts_count) == len(chunks)

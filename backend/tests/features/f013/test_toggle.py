"""F-013 启停 PATCH：列表仍在、不删切片与原文。禁止 drop_all 运行时业务库。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config import get_settings
from src.db.models import KnowledgeChunk, KnowledgeDocument, QaPair
from src.main import app as runtime_app
from src.services.embedding import EmbeddingError

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


def _patch_path(document_id: int) -> str:
    return PATCH_PATH.format(document_id=document_id)


async def _fake_embed(_self: object, texts: list[str]) -> list[list[float]]:
    dim = get_settings().embedding_dimensions
    return [[0.01] * dim for _ in texts]


async def _upload_enabled(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    filename: str = "VPN接入说明.md",
) -> dict[str, Any]:
    monkeypatch.setattr(
        "src.services.knowledge.EmbeddingClient.embed_texts",
        _fake_embed,
    )
    response = await client.post(
        UPLOAD_PATH,
        headers=auth_headers,
        files={"file": (filename, VPN_MARKDOWN.encode("utf-8"), "text/markdown")},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "enabled"
    return data


def test_patch_route_mounted_on_runtime_app() -> None:
    matched = False
    for route in runtime_app.routes:
        path = getattr(route, "path", None)
        methods: set[str] = set(getattr(route, "methods", None) or [])
        if path == "/api/knowledge_documents/{document_id}" and "PATCH" in methods:
            matched = True
            break
    assert matched


def test_toggle_does_not_touch_runtime_db(isolated_db_file: Path) -> None:
    assert isolated_db_file.resolve() != RUNTIME_DB.resolve()


async def test_patch_requires_auth(client: AsyncClient) -> None:
    response = await client.patch(_patch_path(1), json={"enabled": False})
    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHORIZED", "message": "未认证", "data": None}


async def test_patch_missing_enabled_is_validation_error(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.patch(_patch_path(1), headers=auth_headers, json={})
    assert response.status_code == 400
    assert response.json() == {
        "code": "VALIDATION_ERROR",
        "message": "参数验证失败",
        "data": None,
    }


async def test_patch_unknown_document_not_found(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.patch(_patch_path(999), headers=auth_headers, json={"enabled": False})
    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND", "message": "资源不存在", "data": None}


async def test_disable_keeps_row_chunks_and_file(
    client: AsyncClient,
    auth_headers: dict[str, str],
    isolated_session_maker: async_sessionmaker[AsyncSession],
    isolated_upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uploaded = await _upload_enabled(client, auth_headers, monkeypatch)
    document_id = int(uploaded["id"])
    stored = isolated_upload_dir / f"{document_id}.md"
    assert stored.is_file()

    async with isolated_session_maker() as db:
        chunk_count = (
            await db.execute(
                select(func.count())
                .select_from(KnowledgeChunk)
                .where(KnowledgeChunk.document_id == document_id)
            )
        ).scalar_one()
        qa_count = (
            await db.execute(
                select(func.count()).select_from(QaPair).where(QaPair.document_id == document_id)
            )
        ).scalar_one()
        assert int(chunk_count) >= 1
        assert int(qa_count) >= 1

    response = await client.patch(
        _patch_path(document_id),
        headers=auth_headers,
        json={"enabled": False},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert data["id"] == document_id
    assert data["filename"] == "VPN接入说明.md"
    assert data["status"] == "disabled"
    assert data["updated_at"].endswith("Z")
    assert "storage_path" not in data

    listed = await client.get(LIST_PATH, headers=auth_headers)
    assert listed.status_code == 200
    page = listed.json()["data"]
    assert page["total_items"] == 1
    assert len(page["items"]) == 1
    assert page["items"][0]["id"] == document_id
    assert page["items"][0]["status"] == "disabled"
    assert page["items"][0]["filename"] == "VPN接入说明.md"

    assert stored.is_file()
    assert stored.read_text(encoding="utf-8") == VPN_MARKDOWN

    async with isolated_session_maker() as db:
        document = (
            await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == document_id))
        ).scalar_one()
        assert document.status == "disabled"
        chunks_after = (
            await db.execute(
                select(func.count())
                .select_from(KnowledgeChunk)
                .where(KnowledgeChunk.document_id == document_id)
            )
        ).scalar_one()
        qa_after = (
            await db.execute(
                select(func.count()).select_from(QaPair).where(QaPair.document_id == document_id)
            )
        ).scalar_one()
        assert int(chunks_after) == int(chunk_count)
        assert int(qa_after) == int(qa_count)


async def test_disable_is_idempotent(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uploaded = await _upload_enabled(client, auth_headers, monkeypatch)
    document_id = int(uploaded["id"])
    first = await client.patch(
        _patch_path(document_id),
        headers=auth_headers,
        json={"enabled": False},
    )
    assert first.status_code == 200
    assert first.json()["data"]["status"] == "disabled"
    first_updated = first.json()["data"]["updated_at"]

    second = await client.patch(
        _patch_path(document_id),
        headers=auth_headers,
        json={"enabled": False},
    )
    assert second.status_code == 200
    assert second.json()["data"]["status"] == "disabled"
    assert second.json()["data"]["updated_at"] == first_updated


async def test_reenable_after_disable(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uploaded = await _upload_enabled(client, auth_headers, monkeypatch)
    document_id = int(uploaded["id"])
    disabled = await client.patch(
        _patch_path(document_id),
        headers=auth_headers,
        json={"enabled": False},
    )
    assert disabled.json()["data"]["status"] == "disabled"

    enabled = await client.patch(
        _patch_path(document_id),
        headers=auth_headers,
        json={"enabled": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["data"]["status"] == "enabled"

    listed = await client.get(LIST_PATH, headers=auth_headers)
    assert listed.json()["data"]["items"][0]["id"] == document_id
    assert listed.json()["data"]["items"][0]["status"] == "enabled"


async def test_failed_document_cannot_toggle(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(_self: object, _texts: list[str]) -> list[list[float]]:
        raise EmbeddingError("向量化调用失败")

    monkeypatch.setattr("src.services.knowledge.EmbeddingClient.embed_texts", boom)
    uploaded = await client.post(
        UPLOAD_PATH,
        headers=auth_headers,
        files={"file": ("VPN接入说明.md", VPN_MARKDOWN.encode("utf-8"), "text/markdown")},
    )
    assert uploaded.json()["data"]["status"] == "failed"
    document_id = int(uploaded.json()["data"]["id"])

    response = await client.patch(
        _patch_path(document_id),
        headers=auth_headers,
        json={"enabled": True},
    )
    assert response.status_code == 409
    assert response.json() == {
        "code": "CONFLICT",
        "message": "未生效文档不能启停",
        "data": None,
    }


async def test_processing_document_cannot_toggle(
    client: AsyncClient,
    auth_headers: dict[str, str],
    isolated_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with isolated_session_maker() as db:
        row = KnowledgeDocument(
            filename="处理中.md",
            storage_path="pending",
            status="processing",
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        document_id = row.id

    response = await client.patch(
        _patch_path(document_id),
        headers=auth_headers,
        json={"enabled": False},
    )
    assert response.status_code == 409
    assert response.json() == {
        "code": "CONFLICT",
        "message": "未生效文档不能启停",
        "data": None,
    }

    listed = await client.get(LIST_PATH, headers=auth_headers)
    items = listed.json()["data"]["items"]
    assert any(item["id"] == document_id and item["status"] == "processing" for item in items)

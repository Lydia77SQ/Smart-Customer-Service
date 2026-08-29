"""GET /health 与路由骨架：不触发 lifespan，禁止污染运行时业务库。"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.routes.auth import router as auth_router
from src.api.routes.knowledge_documents import router as knowledge_documents_router
from src.api.routes.tickets import router as tickets_router
from src.main import app


@pytest.fixture
async def health_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        trust_env=False,
    ) as client:
        yield client


async def test_health_returns_200(health_client: AsyncClient) -> None:
    response = await health_client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"


def test_route_prefixes_match_tech_spec_resource_words() -> None:
    assert auth_router.router.prefix == "/api/auth"
    assert tickets_router.router.prefix == "/api/tickets"
    assert knowledge_documents_router.router.prefix == "/api/knowledge_documents"

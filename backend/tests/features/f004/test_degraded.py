"""F-004 外部能力不可用时降级，返回 DEGRADED_QA_MESSAGE。"""

from __future__ import annotations

import os

import pytest
from httpx import AsyncClient

from src.core.config import get_settings
from src.services.embedding import EmbeddingError, is_embedding_key_configured
from src.services.llm import parse_chat_content
from src.services.rerank import parse_rerank_indices

from .conftest import MESSAGES_PATH

pytestmark = pytest.mark.timeout(300)


async def _fail_embed(_self: object, texts: list[str]) -> list[list[float]]:
    del texts
    raise EmbeddingError("向量化服务未配置")


def test_parse_chat_content_uses_probed_openai_shape() -> None:
    content = parse_chat_content(
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "message": {"content": "好", "role": "assistant"},
                }
            ],
            "object": "chat.completion",
        }
    )
    assert content == "好"


def test_parse_rerank_indices_uses_native_output_results() -> None:
    ranked = parse_rerank_indices(
        {
            "output": {
                "results": [
                    {"index": 1, "relevance_score": 0.9},
                    {"index": 0, "relevance_score": 0.2},
                ]
            }
        }
    )
    assert ranked[0][0] == 1
    assert ranked[1][0] == 0


async def test_external_unavailable_returns_degraded_message(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.qa_pipeline.EmbeddingClient.embed_texts", _fail_embed)
    expected = get_settings().degraded_qa_message
    response = await client.post(
        MESSAGES_PATH,
        headers=auth_headers,
        json={"content": "打印机无法连接。", "ticket_id": None},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["qa_result_type"] == "degraded"
    assert data["system_message"]["content"] == expected
    assert data["system_message"]["content"] == "很抱歉，您的问题我暂时无法解答，请转人工等待对接人接入"
    assert data["ticket"]["status"] == "ai_assisting"


@pytest.mark.skipif(not os.getenv("REAL_API_TEST"), reason="REAL_API_TEST not set")
async def test_real_chat_structure_when_enabled() -> None:
    """仅 REAL_API_TEST=1 时打真实 Chat；默认 pytest 不调用。"""
    settings = get_settings()
    assert is_embedding_key_configured(settings.dashscope_api_key) is True
    from src.services.llm import LlmClient

    text = await LlmClient().complete(
        [{"role": "user", "content": "只回复一个字：好"}],
        temperature=0.1,
    )
    assert isinstance(text, str)
    assert len(text) >= 1

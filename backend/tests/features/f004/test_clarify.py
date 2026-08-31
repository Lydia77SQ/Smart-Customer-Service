"""F-004 意图模糊只反问，不给出知识生成答案。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.core.config import get_settings
from src.services.qa_pipeline import last_result_type_from_profile, parse_intent_payload

from .conftest import MESSAGES_PATH

pytestmark = pytest.mark.timeout(300)

CLARIFY_TEXT = "请补充你用的是 Windows 还是 Mac，以及大约从什么时候开始失败。"


def _unit_vector() -> list[float]:
    dim = get_settings().embedding_dimensions
    return [1.0] + [0.0] * (dim - 1)


async def _fake_embed(_self: object, texts: list[str]) -> list[list[float]]:
    return [_unit_vector() for _ in texts]


async def _fake_intent(_self: object, messages: list[dict[str, str]], *, temperature: float) -> str:
    del temperature
    joined = " ".join(item["content"] for item in messages)
    if "改写成" in joined or "知识片段" in joined:
        raise AssertionError("意图模糊不得进入改写或生成")
    return f'{{"intent":"ambiguous","question":"{CLARIFY_TEXT}"}}'


def test_parse_intent_ambiguous_and_clear() -> None:
    intent, question = parse_intent_payload(
        '```json\n{"intent":"ambiguous","question":"请补充操作系统"}\n```'
    )
    assert intent == "ambiguous"
    assert question == "请补充操作系统"
    clear, none = parse_intent_payload('{"intent":"clear"}')
    assert clear == "clear"
    assert none is None


async def test_ambiguous_intent_only_clarifies(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.qa_pipeline.EmbeddingClient.embed_texts", _fake_embed)
    monkeypatch.setattr("src.services.qa_pipeline.LlmClient.complete", _fake_intent)

    response = await client.post(
        MESSAGES_PATH,
        headers=auth_headers,
        json={"content": "公司 VPN 连不上，提示认证失败。", "ticket_id": None},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["qa_result_type"] == "clarification"
    assert data["system_message"]["content"] == CLARIFY_TEXT
    assert "门户" not in data["system_message"]["content"]
    assert "制度" not in data["system_message"]["content"] or "请补充" in data["system_message"]["content"]


def test_last_result_type_from_profile() -> None:
    assert last_result_type_from_profile("{}") is None
    assert last_result_type_from_profile('{"last_result_type":"clarification"}') == "clarification"


async def test_second_ambiguous_after_clarification_degrades(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.qa_pipeline.EmbeddingClient.embed_texts", _fake_embed)
    monkeypatch.setattr("src.services.qa_pipeline.LlmClient.complete", _fake_intent)

    first = await client.post(
        MESSAGES_PATH,
        headers=auth_headers,
        json={"content": "公司 VPN 连不上，提示认证失败。", "ticket_id": None},
    )
    assert first.status_code == 200
    ticket_id = first.json()["data"]["ticket"]["id"]
    assert first.json()["data"]["qa_result_type"] == "clarification"

    second = await client.post(
        MESSAGES_PATH,
        headers=auth_headers,
        json={"content": "Windows，今天开始。", "ticket_id": ticket_id},
    )
    assert second.status_code == 200
    data = second.json()["data"]
    assert data["qa_result_type"] == "degraded"
    assert data["system_message"]["content"] == get_settings().degraded_qa_message
    assert data["system_message"]["content"] != CLARIFY_TEXT


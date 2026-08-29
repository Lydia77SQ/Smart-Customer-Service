"""百炼 Text Embedding：httpx 直调，禁止 dashscope SDK。"""

from __future__ import annotations

import httpx
from pycore.core import get_logger

from src.core.config import AppSettings, get_settings

logger = get_logger()

# .env.example 占位，不视为可用密钥。
_PLACEHOLDER_KEYS = frozenset({"your-dashscope-api-key", "change-me"})
# 官方文档 text-embedding-v3 单次最多 10 条。
_EMBEDDING_BATCH_MAX = 10


class EmbeddingError(Exception):
    """向量化失败，由入库流水线转为文档 status=failed。"""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def is_embedding_key_configured(api_key: str) -> bool:
    """判断 DASHSCOPE_API_KEY 是否为可用值（非空、非 example 占位）。"""
    value = api_key.strip()
    if not value:
        return False
    return value.lower() not in _PLACEHOLDER_KEYS


class EmbeddingClient:
    """POST {EMBEDDING_BASE_URL}，解析 output.embeddings[].embedding。"""

    def is_configured(self) -> bool:
        return is_embedding_key_configured(get_settings().dashscope_api_key)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.is_configured():
            logger.warning("跳过百炼 Embedding：API Key 未配置或为占位值")
            raise EmbeddingError("向量化服务未配置")

        settings = get_settings()
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _EMBEDDING_BATCH_MAX):
            batch = texts[start : start + _EMBEDDING_BATCH_MAX]
            vectors.extend(await self._embed_batch(batch, settings))
        if len(vectors) != len(texts):
            raise EmbeddingError("向量化返回条数与输入不一致")
        return vectors

    async def _embed_batch(self, texts: list[str], settings: AppSettings) -> list[list[float]]:
        headers = {
            "Authorization": f"Bearer {settings.dashscope_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.embedding_model,
            "input": {"texts": texts},
            "parameters": {"dimension": settings.embedding_dimensions},
        }
        try:
            async with httpx.AsyncClient(
                trust_env=settings.http_client_trust_env,
                timeout=settings.embedding_timeout_seconds,
            ) as client:
                response = await client.post(
                    settings.embedding_base_url,
                    json=payload,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            logger.error("百炼 Embedding 超时", error_msg=str(exc))
            raise EmbeddingError("向量化调用超时") from exc
        except httpx.HTTPError as exc:
            logger.error("百炼 Embedding 网络错误", error_msg=str(exc))
            raise EmbeddingError("向量化调用失败") from exc

        try:
            body = response.json()
        except ValueError as exc:
            logger.error(
                "百炼 Embedding 响应不是 JSON",
                status_code=response.status_code,
            )
            raise EmbeddingError("向量化响应不是 JSON") from exc

        logger.info(
            "调用百炼 Embedding 完成",
            status_code=response.status_code,
            body_type=type(body).__name__,
        )
        if response.status_code != 200:
            logger.error("百炼 Embedding HTTP 失败", status_code=response.status_code)
            raise EmbeddingError("向量化调用失败")
        return _parse_embeddings(body, expected_dim=settings.embedding_dimensions)


def _parse_embeddings(body: object, *, expected_dim: int) -> list[list[float]]:
    if not isinstance(body, dict):
        raise EmbeddingError("向量化响应结构无效")
    code = body.get("code")
    if code not in (None, "", "Success", 200):
        logger.error("百炼 Embedding 业务失败", api_code=str(code))
        raise EmbeddingError("向量化调用失败")
    output = body.get("output")
    if not isinstance(output, dict):
        raise EmbeddingError("向量化响应缺少 output")
    items = output.get("embeddings")
    if not isinstance(items, list) or not items:
        raise EmbeddingError("向量化响应缺少 embeddings")
    ordered = sorted(
        items,
        key=lambda item: item.get("text_index", 0) if isinstance(item, dict) else 0,
    )
    vectors: list[list[float]] = []
    for item in ordered:
        if not isinstance(item, dict):
            raise EmbeddingError("向量化响应条目无效")
        raw = item.get("embedding")
        if not isinstance(raw, list) or not raw:
            raise EmbeddingError("向量化响应缺少 embedding")
        try:
            vector = [float(value) for value in raw]
        except (TypeError, ValueError) as exc:
            raise EmbeddingError("向量化响应维度解析失败") from exc
        if len(vector) != expected_dim:
            raise EmbeddingError("向量化维度与配置不一致")
        vectors.append(vector)
    return vectors

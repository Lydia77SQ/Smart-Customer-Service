"""百炼 Text Rerank：httpx 直调，禁止 dashscope SDK。"""

from __future__ import annotations

import httpx
from pycore.core import get_logger

from src.core.config import get_settings
from src.services.embedding import is_embedding_key_configured

logger = get_logger()


class RerankError(Exception):
    """重排失败，答疑链路转为 degraded。"""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class RerankClient:
    """POST {RERANK_BASE_URL}，解析 output.results[].index / relevance_score。"""

    def is_configured(self) -> bool:
        return is_embedding_key_configured(get_settings().dashscope_api_key)

    async def rerank(self, query: str, documents: list[str], *, top_n: int) -> list[int]:
        if not documents:
            return []
        if not self.is_configured():
            logger.warning("跳过百炼 Rerank：API Key 未配置或为占位值")
            raise RerankError("重排服务未配置")

        settings = get_settings()
        headers = {
            "Authorization": f"Bearer {settings.dashscope_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.rerank_model,
            "input": {"query": query, "documents": documents},
            "parameters": {"top_n": top_n},
        }
        try:
            async with httpx.AsyncClient(
                trust_env=settings.http_client_trust_env,
                timeout=settings.rerank_timeout_seconds,
            ) as client:
                response = await client.post(
                    settings.rerank_base_url,
                    json=payload,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            logger.error("百炼 Rerank 超时", error_msg=str(exc))
            raise RerankError("重排调用超时") from exc
        except httpx.HTTPError as exc:
            logger.error("百炼 Rerank 网络错误", error_msg=str(exc))
            raise RerankError("重排调用失败") from exc

        try:
            body = response.json()
        except ValueError as exc:
            logger.error("百炼 Rerank 响应不是 JSON", status_code=response.status_code)
            raise RerankError("重排响应不是 JSON") from exc

        logger.info(
            "调用百炼 Rerank 完成",
            status_code=response.status_code,
            body_type=type(body).__name__,
        )
        if response.status_code != 200:
            logger.error("百炼 Rerank HTTP 失败", status_code=response.status_code)
            raise RerankError("重排调用失败")
        ranked = parse_rerank_indices(body)
        return [index for index, _score in ranked[:top_n]]


def parse_rerank_indices(body: object) -> list[tuple[int, float]]:
    """解析原生 DashScope rerank JSON：output.results[].index / relevance_score。"""
    if not isinstance(body, dict):
        raise RerankError("重排响应结构无效")
    code = body.get("code")
    if code not in (None, "", "Success", 200):
        logger.error("百炼 Rerank 业务失败", api_code=str(code))
        raise RerankError("重排调用失败")
    results = _extract_results(body)
    if not isinstance(results, list) or not results:
        raise RerankError("重排响应缺少 results")
    ranked: list[tuple[int, float]] = []
    for item in results:
        if not isinstance(item, dict):
            raise RerankError("重排响应条目无效")
        index = item.get("index")
        score = item.get("relevance_score")
        if not isinstance(index, int):
            raise RerankError("重排响应缺少 index")
        try:
            ranked.append((index, float(score) if score is not None else 0.0))
        except (TypeError, ValueError) as exc:
            raise RerankError("重排响应分数解析失败") from exc
    ranked.sort(key=lambda pair: pair[1], reverse=True)
    return ranked


def _extract_results(body: dict[str, object]) -> object:
    output = body.get("output")
    if isinstance(output, dict):
        return output.get("results")
    return body.get("results")

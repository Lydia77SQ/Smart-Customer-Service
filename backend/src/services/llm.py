"""百炼 Chat Completions：httpx 直调，禁止 dashscope SDK。"""

from __future__ import annotations

import httpx
from pycore.core import get_logger

from src.core.config import get_settings
from src.services.embedding import is_embedding_key_configured

logger = get_logger()


class LlmError(Exception):
    """对话调用失败，答疑链路转为 degraded。"""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class LlmClient:
    """POST {LLM_BASE_URL}/chat/completions，解析 choices[0].message.content。"""

    def is_configured(self) -> bool:
        return is_embedding_key_configured(get_settings().dashscope_api_key)

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
    ) -> str:
        if not self.is_configured():
            logger.warning("跳过百炼 Chat：API Key 未配置或为占位值")
            raise LlmError("对话服务未配置")

        settings = get_settings()
        url = settings.llm_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.dashscope_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": temperature,
        }
        try:
            async with httpx.AsyncClient(
                trust_env=settings.http_client_trust_env,
                timeout=settings.llm_timeout_seconds,
            ) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            logger.error("百炼 Chat 超时", error_msg=str(exc))
            raise LlmError("对话调用超时") from exc
        except httpx.HTTPError as exc:
            logger.error("百炼 Chat 网络错误", error_msg=str(exc))
            raise LlmError("对话调用失败") from exc

        try:
            body = response.json()
        except ValueError as exc:
            logger.error("百炼 Chat 响应不是 JSON", status_code=response.status_code)
            raise LlmError("对话响应不是 JSON") from exc

        logger.info(
            "调用百炼 Chat 完成",
            status_code=response.status_code,
            body_type=type(body).__name__,
        )
        if response.status_code != 200:
            logger.error("百炼 Chat HTTP 失败", status_code=response.status_code)
            raise LlmError("对话调用失败")
        return parse_chat_content(body)


def parse_chat_content(body: object) -> str:
    """解析 OpenAI 兼容 Chat Completions JSON。结构已用真实调用确认。"""
    if not isinstance(body, dict):
        raise LlmError("对话响应结构无效")
    error = body.get("error")
    if isinstance(error, dict):
        logger.error("百炼 Chat 业务失败", api_code=str(error.get("code", "")))
        raise LlmError("对话调用失败")
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LlmError("对话响应缺少 choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise LlmError("对话响应 choices 无效")
    message = first.get("message")
    if not isinstance(message, dict):
        raise LlmError("对话响应缺少 message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise LlmError("对话响应缺少 content")
    return content.strip()

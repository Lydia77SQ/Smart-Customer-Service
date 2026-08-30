"""共用答疑链路 tech-spec §5.1：直出 / 反问 / 生成 / 降级。"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Literal

from pycore.core import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.db.models import KnowledgeChunk, Message, QaPair
from src.repositories.knowledge import KnowledgeChunkRepository, QaPairRepository
from src.services.embedding import EmbeddingClient, EmbeddingError
from src.services.knowledge import unpack_embedding
from src.services.llm import LlmClient, LlmError
from src.services.rerank import RerankClient, RerankError

logger = get_logger()

QaPath = Literal["direct_answer", "clarification", "generated_answer", "degraded"]

_INTENT_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_INTENT_SYSTEM = (
    "你是企业内部 IT/行政客服的意图分类器。"
    "判断员工问题是否信息充足、能否检索制度作答。"
    "只输出 JSON，不要其它文字。格式二选一："
    '{"intent":"clear"} 或 {"intent":"ambiguous","question":"请补充……"}。'
    "缺少系统、地点、时间、对象等关键约束，或问题过于宽泛时判为 ambiguous。"
)

_REWRITE_SYSTEM = (
    "你是企业内部客服检索改写器。"
    "根据长期画像与最近对话，把当前问题改写成一句独立的检索问句。"
    "只输出改写后的问句，不要解释。"
)

_GENERATE_SYSTEM = (
    "你是企业内部 IT/行政客服。"
    "只能依据给定知识片段作答，不得编造制度，不得提及片段中未出现的文档名。"
    "若片段无法回答，明确说明当前知识不足以作答，建议补充信息或转人工。"
)

_CLARIFY_FALLBACK = "请补充更多细节，以便为你查找制度。"


@dataclass(frozen=True)
class QaResult:
    result_type: QaPath
    content: str


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for a, b in zip(left, right, strict=True):
        dot += a * b
        left_norm += a * a
        right_norm += b * b
    if left_norm <= 0.0 or right_norm <= 0.0:
        return 0.0
    return dot / math.sqrt(left_norm * right_norm)


def rrf_fuse(vector_ids: list[int], fts_ids: list[int], *, rrf_k: int) -> list[int]:
    scores: dict[int, float] = {}
    for rank, chunk_id in enumerate(vector_ids, start=1):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    for rank, chunk_id in enumerate(fts_ids, start=1):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    return [item[0] for item in sorted(scores.items(), key=lambda pair: pair[1], reverse=True)]


def parse_intent_payload(raw: str) -> tuple[str, str | None]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = _INTENT_JSON_RE.search(text)
    if match is None:
        raise LlmError("意图识别结果无法解析")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LlmError("意图识别结果不是 JSON") from exc
    if not isinstance(data, dict):
        raise LlmError("意图识别结果结构无效")
    intent = data.get("intent")
    if intent == "ambiguous":
        question = data.get("question")
        if isinstance(question, str) and question.strip():
            return "ambiguous", question.strip()
        return "ambiguous", _CLARIFY_FALLBACK
    if intent == "clear":
        return "clear", None
    raise LlmError("意图识别结果无效")


def apply_profile_rules(profile_json: str, query: str, result_type: str) -> str:
    """每轮规则更新长期画像：保留最近问题，界面不展示。"""
    try:
        data = json.loads(profile_json or "{}")
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    questions = data.get("recent_questions")
    if not isinstance(questions, list):
        questions = []
    questions.append(query[:200])
    data["recent_questions"] = questions[-10:]
    data["last_result_type"] = result_type
    return json.dumps(data, ensure_ascii=False)


def _recent_dialogue(messages: list[Message], rounds: int) -> str:
    tail = messages[-(rounds * 2) :] if rounds > 0 else []
    lines: list[str] = []
    for item in tail:
        role = "员工" if item.sender_type == "employee" else "系统"
        lines.append(f"{role}：{item.content}")
    return "\n".join(lines)


class QaPipeline:
    def __init__(
        self,
        db: AsyncSession,
        *,
        embedding: EmbeddingClient | None = None,
        llm: LlmClient | None = None,
        rerank: RerankClient | None = None,
    ) -> None:
        self.db = db
        self.qa_pairs = QaPairRepository(db)
        self.chunks = KnowledgeChunkRepository(db)
        self.embedding = embedding if embedding is not None else EmbeddingClient()
        self.llm = llm if llm is not None else LlmClient()
        self.rerank = rerank if rerank is not None else RerankClient()

    async def run(
        self,
        *,
        query: str,
        profile_json: str,
        recent_messages: list[Message],
    ) -> QaResult:
        settings = get_settings()
        try:
            return await self._run(
                query=query,
                profile_json=profile_json,
                recent_messages=recent_messages,
            )
        except (EmbeddingError, LlmError, RerankError) as exc:
            logger.warning("答疑链路降级", error_msg=str(exc))
            return QaResult("degraded", settings.degraded_qa_message)

    async def _run(
        self,
        *,
        query: str,
        profile_json: str,
        recent_messages: list[Message],
    ) -> QaResult:
        settings = get_settings()
        query_vector = (await self.embedding.embed_texts([query]))[0]

        direct = await self._match_direct_answer(query_vector)
        if direct is not None:
            return direct

        intent, clarify = await self._classify_intent(query)
        if intent == "ambiguous":
            return QaResult("clarification", clarify or _CLARIFY_FALLBACK)

        rewritten = await self._rewrite_query(
            query=query,
            profile_json=profile_json,
            recent_messages=recent_messages,
        )
        rewritten_vector = (await self.embedding.embed_texts([rewritten]))[0]
        snippets = await self._hybrid_retrieve(rewritten, rewritten_vector)
        if not snippets:
            answer = await self._generate(rewritten, [])
            return QaResult("generated_answer", answer)
        reranked = await self.rerank.rerank(
            rewritten,
            snippets,
            top_n=settings.rerank_top_n,
        )
        selected = [snippets[index] for index in reranked if 0 <= index < len(snippets)]
        if not selected:
            selected = snippets[: settings.rerank_top_n]
        answer = await self._generate(rewritten, selected)
        return QaResult("generated_answer", answer)

    async def _match_direct_answer(self, query_vector: list[float]) -> QaResult | None:
        settings = get_settings()
        pairs = await self.qa_pairs.list_enabled()
        best: tuple[float, QaPair] | None = None
        for pair in pairs:
            vector = unpack_embedding(pair.embedding)
            if vector is None:
                continue
            score = cosine_similarity(query_vector, vector)
            if best is None or score > best[0]:
                best = (score, pair)
        if best is not None and best[0] >= settings.qa_similarity_threshold:
            return QaResult("direct_answer", best[1].answer)
        return None

    async def _classify_intent(self, query: str) -> tuple[str, str | None]:
        settings = get_settings()
        raw = await self.llm.complete(
            [
                {"role": "system", "content": _INTENT_SYSTEM},
                {"role": "user", "content": query},
            ],
            temperature=settings.llm_temperature_intent,
        )
        return parse_intent_payload(raw)

    async def _rewrite_query(
        self,
        *,
        query: str,
        profile_json: str,
        recent_messages: list[Message],
    ) -> str:
        settings = get_settings()
        history = _recent_dialogue(recent_messages, settings.short_term_memory_rounds)
        user = (
            f"长期画像：{profile_json or '{}'}\n"
            f"最近对话：{history or '（无）'}\n"
            f"当前问题：{query}"
        )
        rewritten = await self.llm.complete(
            [
                {"role": "system", "content": _REWRITE_SYSTEM},
                {"role": "user", "content": user},
            ],
            temperature=settings.llm_temperature_intent,
        )
        return rewritten.strip() or query

    async def _hybrid_retrieve(
        self, rewritten: str, query_vector: list[float]
    ) -> list[str]:
        settings = get_settings()
        chunks = await self.chunks.list_enabled()
        scored: list[tuple[float, KnowledgeChunk]] = []
        for chunk in chunks:
            vector = unpack_embedding(chunk.embedding)
            if vector is None:
                continue
            scored.append((cosine_similarity(query_vector, vector), chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        vector_ids = [item[1].id for item in scored[: settings.search_top_k]]
        fts_ids = await self.chunks.search_fts_ids(rewritten, top_k=settings.search_top_k)
        fused_ids = rrf_fuse(vector_ids, fts_ids, rrf_k=settings.rrf_k)
        by_id = {chunk.id: chunk for chunk in chunks}
        contents: list[str] = []
        for chunk_id in fused_ids:
            matched = by_id.get(chunk_id)
            if matched is not None and matched.content.strip():
                contents.append(matched.content)
        return contents

    async def _generate(self, query: str, snippets: list[str]) -> str:
        settings = get_settings()
        knowledge = "\n\n".join(snippets) if snippets else "（无可用知识片段）"
        raw = await self.llm.complete(
            [
                {"role": "system", "content": _GENERATE_SYSTEM},
                {"role": "user", "content": f"知识片段：\n{knowledge}\n\n问题：{query}"},
            ],
            temperature=settings.llm_temperature_generation,
        )
        return raw.strip()

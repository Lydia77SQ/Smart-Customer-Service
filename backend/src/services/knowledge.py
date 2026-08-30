"""知识文档上传入库、列表与启停。失败不得 status=enabled；停用不删切片。"""

from __future__ import annotations

import re
import struct
from pathlib import Path

from pycore.core import get_logger

from src.core.config import BACKEND_ROOT, get_settings
from src.db.models import KnowledgeDocument
from src.models.knowledge import KnowledgeDocumentOut, KnowledgeDocumentStatus
from src.repositories.knowledge import (
    KnowledgeChunkRepository,
    KnowledgeDocumentRepository,
    QaPairRepository,
)
from src.services.embedding import EmbeddingClient, EmbeddingError

logger = get_logger()

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_MARKDOWN_SUFFIX = ".md"


RETRIEVAL_ENABLED_STATUS = "enabled"
_TOGGLEABLE_STATUSES = frozenset({"enabled", "disabled"})
_NOT_FOUND_MESSAGE = "资源不存在"
_TOGGLE_CONFLICT_MESSAGE = "未生效文档不能启停"


class KnowledgeValidationError(Exception):
    """上传参数不合法，路由转为 400 VALIDATION_ERROR。"""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class KnowledgeNotFoundError(Exception):
    """文档不存在，路由转为 404 NOT_FOUND。"""

    def __init__(self, message: str = _NOT_FOUND_MESSAGE) -> None:
        self.message = message
        super().__init__(message)


class KnowledgeToggleConflictError(Exception):
    """failed / processing 不可启停，路由转为 409 CONFLICT。"""

    def __init__(self, message: str = _TOGGLE_CONFLICT_MESSAGE) -> None:
        self.message = message
        super().__init__(message)


def is_enabled_for_retrieval(status: str) -> bool:
    """后续答疑（T-016 / F-004）只使用 enabled 文档；停用不删切片，但不参与检索。"""
    return status == RETRIEVAL_ENABLED_STATUS


def resolve_upload_dir(base_dir: Path | None = None) -> Path:
    """把 UPLOAD_DIR 解析为绝对路径并创建目录。"""
    root = base_dir if base_dir is not None else BACKEND_ROOT
    raw = get_settings().upload_dir
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def pack_embedding(values: list[float]) -> bytes:
    return struct.pack(f"<{len(values)}f", *values)


def unpack_embedding(blob: bytes | None) -> list[float] | None:
    if not blob:
        return None
    if len(blob) % 4 != 0:
        return None
    count = len(blob) // 4
    return list(struct.unpack(f"<{count}f", blob))


def split_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    if chunk_size <= 0:
        return [stripped]
    if len(stripped) <= chunk_size:
        return [stripped]
    step = chunk_size - overlap if overlap < chunk_size else chunk_size
    if step <= 0:
        step = chunk_size
    chunks: list[str] = []
    start = 0
    length = len(stripped)
    while start < length:
        end = min(start + chunk_size, length)
        chunks.append(stripped[start:end])
        if end >= length:
            break
        start += step
    return chunks


def extract_qa_pairs(markdown: str, filename: str) -> list[tuple[str, str]]:
    """从 Markdown 标题结构抽取标准问答；无标题时用文件名作问、全文作答。"""
    pairs: list[tuple[str, str]] = []
    matches = list(_HEADING_RE.finditer(markdown))
    if matches:
        for index, match in enumerate(matches):
            question = match.group(2).strip()
            content_start = match.end()
            content_end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
            answer = markdown[content_start:content_end].strip()
            if question and answer:
                pairs.append((question, answer))
    if not pairs:
        stem = filename[:-3] if filename.lower().endswith(_MARKDOWN_SUFFIX) else filename
        body = markdown.strip()
        if stem and body:
            pairs.append((stem, body))
    return pairs


def original_filename(raw_name: str | None) -> str:
    name = Path(raw_name or "").name.strip()
    return name


def is_markdown_filename(filename: str) -> bool:
    return filename.lower().endswith(_MARKDOWN_SUFFIX)


class KnowledgeService:
    def __init__(
        self,
        documents: KnowledgeDocumentRepository,
        chunks: KnowledgeChunkRepository,
        qa_pairs: QaPairRepository,
        embedding_client: EmbeddingClient | None = None,
    ) -> None:
        self.documents = documents
        self.chunks = chunks
        self.qa_pairs = qa_pairs
        self.embedding = embedding_client if embedding_client is not None else EmbeddingClient()

    def to_out(self, document: KnowledgeDocument) -> KnowledgeDocumentOut:
        return KnowledgeDocumentOut.model_validate(document)

    async def list_documents(
        self, *, page: int, page_size: int
    ) -> tuple[list[KnowledgeDocumentOut], int]:
        rows, total = await self.documents.list_page(page=page, page_size=page_size)
        return [self.to_out(row) for row in rows], total

    async def list_enabled_document_ids(self) -> list[int]:
        """T-016 检索入口：只返回 enabled 文档 ID，disabled/failed/processing 均排除。"""
        return await self.documents.list_enabled_ids()

    async def toggle(self, document_id: int, enabled: bool) -> KnowledgeDocumentOut:
        document = await self.documents.get_by_id(document_id)
        if document is None:
            raise KnowledgeNotFoundError()
        if document.status not in _TOGGLEABLE_STATUSES:
            raise KnowledgeToggleConflictError()
        target: KnowledgeDocumentStatus = "enabled" if enabled else "disabled"
        if document.status == target:
            return self.to_out(document)
        document = await self.documents.mark_status(document, target)
        logger.info(
            "知识文档启停已更新，切片与原文未删除",
            document_id=document.id,
            status=document.status,
        )
        return self.to_out(document)

    async def upload(self, *, filename: str | None, content: bytes) -> KnowledgeDocumentOut:
        display_name = original_filename(filename)
        if not display_name or not is_markdown_filename(display_name):
            raise KnowledgeValidationError("仅支持 Markdown")
        settings = get_settings()
        if len(content) <= 0 or len(content) > settings.knowledge_max_size_bytes:
            raise KnowledgeValidationError("参数验证失败")
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise KnowledgeValidationError("参数验证失败") from exc
        if not text.strip():
            raise KnowledgeValidationError("参数验证失败")

        upload_dir = resolve_upload_dir()
        document = await self.documents.create(
            filename=display_name,
            storage_path="pending",
            status="processing",
        )
        relative_path = f"{document.id}.md"
        try:
            (upload_dir / relative_path).write_bytes(content)
        except OSError as exc:
            logger.error("知识原文落盘失败", document_id=document.id, error_msg=str(exc))
            await self.documents.mark_status(document, "failed")
            return self.to_out(document)
        document = await self.documents.update_storage_path(document, relative_path)
        logger.info("知识原文已保存", document_id=document.id)

        try:
            await self._ingest(document, text)
        except EmbeddingError as exc:
            logger.error(
                "知识入库向量化失败，文档不得启用",
                document_id=document.id,
                error_msg=exc.message,
            )
            document = await self.documents.mark_status(document, "failed")
            return self.to_out(document)
        except Exception as exc:
            logger.error(
                "知识入库处理失败，文档不得启用",
                document_id=document.id,
                error_msg=str(exc),
            )
            document = await self.documents.mark_status(document, "failed")
            return self.to_out(document)

        document = await self.documents.mark_status(document, "enabled")
        logger.info("知识入库成功，文档已启用", document_id=document.id)
        return self.to_out(document)

    async def _ingest(self, document: KnowledgeDocument, text: str) -> None:
        settings = get_settings()
        chunk_texts = split_chunks(text, settings.chunk_size, settings.chunk_overlap)
        qa_items = extract_qa_pairs(text, document.filename)
        if not chunk_texts or not qa_items:
            raise EmbeddingError("无法从文档抽取切片或标准问答")

        embed_inputs = list(chunk_texts) + [question for question, _answer in qa_items]
        vectors = await self.embedding.embed_texts(embed_inputs)
        chunk_vectors = vectors[: len(chunk_texts)]
        qa_vectors = vectors[len(chunk_texts) :]

        await self.chunks.add_many(
            document_id=document.id,
            chunks=[
                (index, content, pack_embedding(chunk_vectors[index]))
                for index, content in enumerate(chunk_texts)
            ],
        )
        await self.qa_pairs.add_many(
            document_id=document.id,
            pairs=[
                (question, answer, pack_embedding(qa_vectors[index]))
                for index, (question, answer) in enumerate(qa_items)
            ],
        )
        logger.info(
            "知识切片与问答已写入并同步 FTS",
            document_id=document.id,
            chunk_count=len(chunk_texts),
            qa_count=len(qa_items),
        )


__all__ = [
    "KnowledgeNotFoundError",
    "KnowledgeService",
    "KnowledgeToggleConflictError",
    "KnowledgeValidationError",
    "RETRIEVAL_ENABLED_STATUS",
    "extract_qa_pairs",
    "is_enabled_for_retrieval",
    "pack_embedding",
    "resolve_upload_dir",
    "split_chunks",
    "unpack_embedding",
]

"""知识文档、切片与标准问答数据访问。"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import KnowledgeChunk, KnowledgeDocument, QaPair, utc_now

_FTS_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+")


class KnowledgeDocumentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        filename: str,
        storage_path: str,
        status: str = "processing",
    ) -> KnowledgeDocument:
        row = KnowledgeDocument(
            filename=filename,
            storage_path=storage_path,
            status=status,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get_by_id(self, document_id: int) -> KnowledgeDocument | None:
        result = await self.db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        return result.scalar_one_or_none()

    async def mark_status(self, document: KnowledgeDocument, status: str) -> KnowledgeDocument:
        document.status = status
        document.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(document)
        return document

    async def update_storage_path(
        self, document: KnowledgeDocument, storage_path: str
    ) -> KnowledgeDocument:
        document.storage_path = storage_path
        document.updated_at = utc_now()
        await self.db.flush()
        await self.db.refresh(document)
        return document

    async def list_enabled_ids(self) -> list[int]:
        """答疑检索只纳入 status=enabled 的文档（T-016 / F-004 约定）。"""
        result = await self.db.execute(
            select(KnowledgeDocument.id).where(KnowledgeDocument.status == "enabled")
        )
        return list(result.scalars().all())

    async def list_page(
        self, *, page: int, page_size: int
    ) -> tuple[list[KnowledgeDocument], int]:
        total = int(
            (await self.db.execute(select(func.count()).select_from(KnowledgeDocument))).scalar_one()
        )
        result = await self.db.execute(
            select(KnowledgeDocument)
            .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total


class KnowledgeChunkRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add_many(
        self,
        *,
        document_id: int,
        chunks: list[tuple[int, str, bytes | None]],
    ) -> list[KnowledgeChunk]:
        rows: list[KnowledgeChunk] = []
        for chunk_index, content, embedding in chunks:
            row = KnowledgeChunk(
                document_id=document_id,
                chunk_index=chunk_index,
                content=content,
                embedding=embedding,
            )
            self.db.add(row)
            rows.append(row)
        await self.db.flush()
        return rows

    async def list_enabled(self) -> list[KnowledgeChunk]:
        """仅 status=enabled 文档的切片，供答疑混合检索。"""
        result = await self.db.execute(
            select(KnowledgeChunk)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .where(KnowledgeDocument.status == "enabled")
        )
        return list(result.scalars().all())

    async def search_fts_ids(self, query: str, *, top_k: int) -> list[int]:
        """FTS5 关键词召回，JOIN 后只保留 enabled 文档切片。"""
        fts_query = _sanitize_fts_query(query)
        if not fts_query:
            return []
        try:
            result = await self.db.execute(
                text(
                    """
                    SELECT kc.id
                    FROM knowledge_chunks_fts AS fts
                    JOIN knowledge_chunks AS kc ON kc.id = fts.chunk_id
                    JOIN knowledge_documents AS kd ON kd.id = kc.document_id
                    WHERE kd.status = 'enabled'
                      AND fts MATCH :q
                    LIMIT :k
                    """
                ),
                {"q": fts_query, "k": top_k},
            )
        except SQLAlchemyError:
            return []
        return [int(row[0]) for row in result.all()]


class QaPairRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add_many(
        self,
        *,
        document_id: int,
        pairs: list[tuple[str, str, bytes | None]],
    ) -> list[QaPair]:
        rows: list[QaPair] = []
        for question, answer, embedding in pairs:
            row = QaPair(
                document_id=document_id,
                question=question,
                answer=answer,
                embedding=embedding,
            )
            self.db.add(row)
            rows.append(row)
        await self.db.flush()
        return rows

    async def list_enabled(self) -> list[QaPair]:
        """仅 status=enabled 文档的标准问答，供高置信直出。"""
        result = await self.db.execute(
            select(QaPair)
            .join(KnowledgeDocument, KnowledgeDocument.id == QaPair.document_id)
            .where(KnowledgeDocument.status == "enabled")
        )
        return list(result.scalars().all())


def _sanitize_fts_query(raw: str) -> str:
    tokens = _FTS_TOKEN_RE.findall(raw)
    if not tokens:
        return ""
    return " OR ".join(f'"{token}"' for token in tokens[:8])

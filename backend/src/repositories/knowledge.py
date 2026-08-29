"""知识文档、切片与标准问答数据访问。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import KnowledgeChunk, KnowledgeDocument, QaPair, utc_now


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

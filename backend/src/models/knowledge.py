"""知识文档 Pydantic 模型，对齐 docs/api-contracts.md API-F012。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer

KnowledgeDocumentStatus = Literal["enabled", "disabled", "failed", "processing"]


def to_iso_z(value: datetime) -> str:
    """UTC ISO-8601，末尾 Z，对齐 api-contracts 时间约定。"""
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class KnowledgeDocumentOut(BaseModel):
    """上传 / 列表条目的契约 DTO；不含 storage_path。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: KnowledgeDocumentStatus
    updated_at: datetime

    @field_serializer("updated_at")
    def serialize_updated_at(self, value: datetime) -> str:
        return to_iso_z(value)

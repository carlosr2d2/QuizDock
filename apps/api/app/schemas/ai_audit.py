from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AiDecisionEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    actor_user_id: UUID | None = None
    actor_email: str | None = None
    actor_full_name: str | None = None
    feature: str
    document_id: UUID | None = None
    conversation_id: UUID | None = None
    model: str = ""
    prompt_hash: str | None = None
    chunk_ids: list = Field(default_factory=list)
    confidence: float | None = None
    relevance: float | None = None
    outcome: str = ""
    payload: dict = Field(default_factory=dict)
    created_at: datetime


class AiDecisionEventList(BaseModel):
    items: list[AiDecisionEventRead] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


class AiAuditPurgeResult(BaseModel):
    deleted: int
    retention_days: int

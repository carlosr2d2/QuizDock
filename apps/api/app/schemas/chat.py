from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ChatSessionCreate(BaseModel):
    exam_id: UUID | None = None
    title: str | None = Field(default=None, max_length=240)


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ChatCitationRead(BaseModel):
    chunk_id: UUID | None = None
    quote: str
    page_start: int | None = None
    page_end: int | None = None
    chapter: str | None = None
    section: str | None = None
    confidence: float | None = None


class ChatMessageRead(ORMModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    citations: list[ChatCitationRead] = Field(default_factory=list)
    refusal: bool = False
    model: str | None = None
    created_at: datetime


class ChatSessionRead(ORMModel):
    id: UUID
    document_id: UUID
    user_id: UUID
    exam_id: UUID | None = None
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatSessionDetail(ChatSessionRead):
    messages: list[ChatMessageRead] = Field(default_factory=list)

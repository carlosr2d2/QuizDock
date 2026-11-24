from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AppealCreate(BaseModel):
    attempt_id: UUID
    question_id: UUID
    argument: str = Field(min_length=1, max_length=4000)
    evidence_quote: str | None = Field(default=None, max_length=2000)
    evidence_chunk_id: UUID | None = None
    evidence_argument: str | None = Field(default=None, max_length=2000)


class AppealEvidenceCreate(BaseModel):
    quote: str = Field(default="", max_length=2000)
    chunk_id: UUID | None = None
    argument: str | None = Field(default=None, max_length=2000)
    page_start: int | None = None
    page_end: int | None = None
    chapter: str | None = Field(default=None, max_length=240)
    section: str | None = Field(default=None, max_length=240)


class AppealStatusUpdate(BaseModel):
    status: str


class AppealResolveRequest(BaseModel):
    decision: str
    rationale: str = Field(min_length=1, max_length=4000)


class AppealEvidenceRead(ORMModel):
    id: UUID
    appeal_id: UUID
    submitted_by_user_id: UUID
    chunk_id: UUID | None = None
    quote: str
    page_start: int | None = None
    page_end: int | None = None
    chapter: str | None = None
    section: str | None = None
    argument: str | None = None
    source: str
    created_at: datetime


class AppealResolutionRead(ORMModel):
    id: UUID
    appeal_id: UUID
    resolver_user_id: UUID
    decision: str
    rationale: str
    score_adjustment: float | None = None
    resolved_at: datetime


class AppealActionRead(ORMModel):
    id: UUID
    appeal_id: UUID
    actor_user_id: UUID | None = None
    action: str
    payload: dict = Field(default_factory=dict)
    created_at: datetime


class AppealRead(ORMModel):
    id: UUID
    organization_id: UUID
    attempt_id: UUID
    question_id: UUID
    exam_id: UUID
    student_user_id: UUID
    status: str
    student_argument: str
    selected_indices: list[int] = Field(default_factory=list)
    correct_indices: list[int] = Field(default_factory=list)
    system_evidence_snapshot: dict = Field(default_factory=dict)
    question_prompt: str = ""
    exam_title: str = ""
    created_at: datetime
    updated_at: datetime
    student_name: str = ""
    student_email: str = ""


class AppealDetail(AppealRead):
    evidence: list[AppealEvidenceRead] = Field(default_factory=list)
    resolution: AppealResolutionRead | None = None
    actions: list[AppealActionRead] = Field(default_factory=list)


class DocumentChunkRead(ORMModel):
    id: UUID
    position: int
    content: str
    page_start: int | None = None
    page_end: int | None = None
    chapter: str | None = None
    section: str | None = None

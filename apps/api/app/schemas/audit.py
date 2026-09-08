from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.audit import AuditAction
from app.models.identity import MembershipRole


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    actor_user_id: UUID | None = None
    actor_email: str | None = None
    actor_full_name: str | None = None
    actor_role: MembershipRole | None = None
    action: AuditAction
    target_type: str
    target_id: UUID | None = None
    summary: str
    payload: dict = Field(default_factory=dict)
    created_at: datetime


class AuditEventList(BaseModel):
    items: list[AuditEventRead] = []
    total: int = 0
    limit: int = 50
    offset: int = 0

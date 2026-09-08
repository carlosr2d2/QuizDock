from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.exam import str_enum
from app.models.identity import MembershipRole
from app.models.mixins import UUIDPrimaryKeyMixin, utcnow


class AuditAction(StrEnum):
    MEMBER_INVITED = "member.invited"
    MEMBER_INVITE_RESENT = "member.invite_resent"
    MEMBER_INVITE_REVOKED = "member.invite_revoked"
    MEMBER_JOINED = "member.joined"
    MEMBER_REMOVED = "member.removed"
    GROUP_CREATED = "group.created"
    GROUP_RENAMED = "group.renamed"
    GROUP_DELETED = "group.deleted"
    GROUP_MEMBERS_UPDATED = "group.members_updated"
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_DELETED = "document.deleted"
    EXAM_GENERATION_REQUESTED = "exam.generation_requested"
    EXAM_ASSIGNED = "exam.assigned"
    EXAM_UNASSIGNED = "exam.unassigned"
    FLASHCARD_GENERATION_REQUESTED = "flashcard.generation_requested"
    ORGANIZATION_CREATED = "organization.created"


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_org_created", "organization_id", "created_at"),
        Index("ix_audit_events_org_action", "organization_id", "action"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_role: Mapped[MembershipRole | None] = mapped_column(
        str_enum(MembershipRole, "membership_role", length=32),
        nullable=True,
    )
    action: Mapped[AuditAction] = mapped_column(str_enum(AuditAction, "audit_action", length=48))
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[UUID | None] = mapped_column(nullable=True)
    summary: Mapped[str] = mapped_column(String(240))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.identity import InvitationStatus, MembershipRole
from app.schemas.auth import AppEmail, ORMModel, OrganizationRead


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)


class InvitationCreate(BaseModel):
    email: AppEmail
    role: MembershipRole = MembershipRole.MEMBER


class MemberRead(ORMModel):
    id: UUID
    user_id: UUID
    email: str
    full_name: str
    role: MembershipRole


class GroupCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class GroupMembersUpdate(BaseModel):
    user_ids: list[UUID] = Field(default_factory=list)


class GroupRead(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    member_count: int
    members: list[MemberRead] = []


class InvitationRead(ORMModel):
    id: UUID
    organization_id: UUID
    email: str
    role: MembershipRole
    status: InvitationStatus
    token: str | None = None
    expires_at: datetime
    created_at: datetime
    email_sent: bool | None = None


class InvitationPublic(BaseModel):
    organization_id: UUID
    organization_name: str
    email: str
    role: MembershipRole
    status: InvitationStatus
    expires_at: datetime


class InvitationAcceptRead(BaseModel):
    organization: OrganizationRead
    role: MembershipRole


class MyInvitationRead(InvitationPublic):
    id: UUID
    token: str


class TeamSnapshot(BaseModel):
    organization: OrganizationRead
    role: MembershipRole
    can_manage: bool
    can_create_content: bool
    can_invite: bool = False
    seat_limit: int | None = None
    seat_used: int = 0
    members: list[MemberRead]
    invitations: list[InvitationRead]
    groups: list[GroupRead] = []

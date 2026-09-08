from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models import MembershipRole
from app.models.audit import AuditAction, AuditEvent
from app.services.audit import AuditService
from app.services.errors import DomainError, ForbiddenError
from app.services.team import TeamService
from tests.fakes import (
    FakeAuditRepo,
    FakeAuditService,
    FakeGroupRepo,
    FakeInvitationRepo,
    FakeMailer,
    FakeMembershipRepo,
    FakeOrgRepo,
    FakeSession,
    FakeUserRepo,
    make_membership,
    make_org,
    make_user,
)


def _team(org) -> TeamService:
    service = TeamService(FakeSession(), mailer=FakeMailer())
    service.orgs = FakeOrgRepo()
    service.orgs.by_id[org.id] = org
    service.orgs.slugs.add(org.slug)
    service.users = FakeUserRepo()
    service.memberships = FakeMembershipRepo()
    service.groups = FakeGroupRepo()
    service.invitations = FakeInvitationRepo()
    service.audit = FakeAuditService()
    return service


def _audit(org) -> AuditService:
    service = AuditService(FakeSession())
    service.orgs = FakeOrgRepo()
    service.orgs.by_id[org.id] = org
    service.repo = FakeAuditRepo()
    return service


def _event(org, action=AuditAction.MEMBER_INVITED, *, actor_id=None) -> AuditEvent:
    now = datetime.now(timezone.utc)
    return AuditEvent(
        id=uuid4(),
        organization_id=org.id,
        actor_user_id=actor_id,
        actor_role=MembershipRole.OWNER,
        action=action,
        target_type="invitation",
        target_id=uuid4(),
        summary="Invitó a ana@empresa.com como member",
        payload={"email": "ana@empresa.com"},
        created_at=now,
    )


@pytest.mark.asyncio
async def test_member_cannot_list_audit():
    org = make_org(is_personal=False)
    service = _audit(org)
    with pytest.raises(ForbiddenError, match="auditoría"):
        await service.list_events(org.id, MembershipRole.MEMBER)


@pytest.mark.asyncio
async def test_personal_workspace_has_no_audit_list():
    org = make_org(is_personal=True)
    service = _audit(org)
    with pytest.raises(DomainError, match="empresa"):
        await service.list_events(org.id, MembershipRole.OWNER)


@pytest.mark.asyncio
async def test_auditor_can_list_audit_for_own_org():
    org = make_org(is_personal=False)
    other = make_org(is_personal=False, slug="otra")
    service = _audit(org)
    service.orgs.by_id[other.id] = other
    own = _event(org)
    leaked = _event(other)
    service.repo.items.extend([own, leaked])

    result = await service.list_events(org.id, MembershipRole.AUDITOR)

    assert result.total == 1
    assert result.items[0].id == own.id
    assert result.items[0].action == AuditAction.MEMBER_INVITED


@pytest.mark.asyncio
async def test_record_skips_personal_workspace():
    org = make_org(is_personal=True)
    service = _audit(org)
    event = await service.record(
        org.id,
        AuditAction.DOCUMENT_DELETED,
        actor_role=MembershipRole.OWNER,
        target_type="document",
        summary="Eliminó un documento",
    )
    assert event is None
    assert service.repo.items == []


@pytest.mark.asyncio
async def test_record_writes_for_team_workspace():
    org = make_org(is_personal=False)
    owner = make_user()
    service = _audit(org)
    event = await service.record(
        org.id,
        AuditAction.DOCUMENT_UPLOADED,
        actor_user_id=owner.id,
        actor_role=MembershipRole.OWNER,
        target_type="document",
        target_id=uuid4(),
        summary="Subió «Guía»",
        payload={"title": "Guía"},
    )
    assert event is not None
    assert event.action == AuditAction.DOCUMENT_UPLOADED
    assert len(service.repo.items) == 1


@pytest.mark.asyncio
async def test_invite_writes_audit_event():
    org = make_org(is_personal=False, slug="acme")
    owner = make_user()
    service = _team(org)

    await service.invite(org.id, owner, MembershipRole.OWNER, "carlos@empresa.com", MembershipRole.MEMBER)

    assert service.audit.events[0]["action"] == AuditAction.MEMBER_INVITED
    assert service.audit.events[0]["payload"]["email"] == "carlos@empresa.com"


@pytest.mark.asyncio
async def test_remove_member_writes_audit_event():
    org = make_org(is_personal=False)
    owner = make_user()
    member = make_user(email="carlos@empresa.com")
    service = _team(org)
    service.users.by_id[member.id] = member
    service.memberships.items = [
        make_membership(owner, org.id, MembershipRole.OWNER),
        make_membership(member, org.id, MembershipRole.MEMBER),
    ]

    await service.remove_member(org.id, owner.id, MembershipRole.OWNER, member.id)

    assert service.audit.events[0]["action"] == AuditAction.MEMBER_REMOVED
    assert service.audit.events[0]["payload"]["email"] == "carlos@empresa.com"

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models import MembershipRole
from app.models.identity import InvitationStatus, PlanTier
from app.services.errors import ConflictError, DomainError, ForbiddenError, NotFoundError
from app.services.mail import MailError
from app.services.team import TeamService
from tests.fakes import (
    FakeGroupRepo,
    FakeInvitationRepo,
    FakeMailer,
    FakeMembershipRepo,
    FakeOrgRepo,
    FakeSession,
    FakeUserRepo,
    FakeAuditService,
    make_membership,
    make_org,
    make_user,
)


def _team(org, mailer: FakeMailer | None = None) -> tuple[TeamService, FakeMailer]:
    resolved = mailer or FakeMailer()
    service = TeamService(FakeSession(), mailer=resolved)
    service.orgs = FakeOrgRepo()
    service.orgs.by_id[org.id] = org
    service.orgs.slugs.add(org.slug)
    service.users = FakeUserRepo()
    service.memberships = FakeMembershipRepo()
    service.groups = FakeGroupRepo()
    service.invitations = FakeInvitationRepo()
    service.audit = FakeAuditService()
    return service, resolved


@pytest.mark.asyncio
async def test_invite_sends_email_with_accept_link():
    org = make_org(name="Acme Capacitación", is_personal=False, slug="acme")
    owner = make_user(full_name="Ana Owner")
    service, mailer = _team(org)

    outcome = await service.invite(
        org.id, owner, MembershipRole.OWNER, "carlos@empresa.com", MembershipRole.MEMBER
    )

    assert outcome.email_sent is True
    assert outcome.invitation.email == "carlos@empresa.com"
    assert len(mailer.sent) == 1
    message = mailer.sent[0]
    assert message.to == "carlos@empresa.com"
    assert "Acme Capacitación" in message.subject
    assert "Ana Owner" in message.text
    assert "miembro" in message.text
    assert f"/invite/{outcome.invitation.token}" in message.text
    assert f"/invite/{outcome.invitation.token}" in message.html


@pytest.mark.asyncio
async def test_reinvite_rotates_token_and_sends_again():
    org = make_org(is_personal=False)
    owner = make_user()
    service, mailer = _team(org)
    first = await service.invite(org.id, owner, MembershipRole.OWNER, "ana@empresa.com", MembershipRole.ADMIN)
    first_token = first.invitation.token
    second = await service.invite(org.id, owner, MembershipRole.OWNER, "ana@empresa.com", MembershipRole.MEMBER)

    assert first.invitation.id == second.invitation.id
    assert first_token != second.invitation.token
    assert second.invitation.role == MembershipRole.MEMBER
    assert len(mailer.sent) == 2
    assert second.invitation.token in mailer.sent[1].text


@pytest.mark.asyncio
async def test_invite_succeeds_when_mailer_fails():
    org = make_org(is_personal=False)
    owner = make_user()
    mailer = FakeMailer()
    mailer.error = MailError("smtp down")
    service, _ = _team(org, mailer)

    outcome = await service.invite(
        org.id, owner, MembershipRole.OWNER, "ana@empresa.com", MembershipRole.MEMBER
    )

    assert outcome.email_sent is False
    assert outcome.invitation.status == InvitationStatus.PENDING
    assert mailer.sent == []


@pytest.mark.asyncio
async def test_invite_skips_email_when_smtp_is_not_configured():
    org = make_org(is_personal=False)
    owner = make_user()
    service, mailer = _team(org, FakeMailer(configured=False))

    outcome = await service.invite(
        org.id, owner, MembershipRole.OWNER, "ana@empresa.com", MembershipRole.MEMBER
    )

    assert outcome.email_sent is False
    assert mailer.sent == []


@pytest.mark.asyncio
async def test_invite_rejects_existing_member_without_sending():
    org = make_org(is_personal=False)
    owner = make_user()
    member = make_user(email="carlos@empresa.com")
    service, mailer = _team(org)
    service.users.by_email[member.email] = member
    service.memberships.items = [make_membership(member, org.id, MembershipRole.MEMBER)]

    with pytest.raises(ConflictError, match="miembro"):
        await service.invite(org.id, owner, MembershipRole.OWNER, member.email, MembershipRole.MEMBER)
    assert mailer.sent == []


@pytest.mark.asyncio
async def test_cannot_invite_self():
    org = make_org(is_personal=False)
    owner = make_user(email="ana@empresa.com")
    service, mailer = _team(org)
    with pytest.raises(DomainError, match="ti mismo"):
        await service.invite(org.id, owner, MembershipRole.OWNER, "Ana@empresa.com", MembershipRole.MEMBER)
    assert mailer.sent == []


@pytest.mark.asyncio
async def test_member_cannot_invite():
    org = make_org(is_personal=False)
    member = make_user()
    service, _ = _team(org)
    with pytest.raises(ForbiddenError):
        await service.invite(org.id, member, MembershipRole.MEMBER, "ana@empresa.com", MembershipRole.MEMBER)


@pytest.mark.asyncio
async def test_personal_workspace_cannot_invite():
    org = make_org(is_personal=True)
    owner = make_user()
    service, _ = _team(org)
    with pytest.raises(DomainError, match="personal"):
        await service.invite(org.id, owner, MembershipRole.OWNER, "ana@empresa.com", MembershipRole.MEMBER)


@pytest.mark.asyncio
async def test_resend_sends_again():
    org = make_org(is_personal=False)
    owner = make_user(full_name="Ana")
    service, mailer = _team(org)
    created = await service.invite(
        org.id, owner, MembershipRole.OWNER, "carlos@empresa.com", MembershipRole.AUDITOR
    )

    outcome = await service.resend(org.id, owner, MembershipRole.OWNER, created.invitation.id)

    assert outcome.email_sent is True
    assert len(mailer.sent) == 2
    assert "auditor" in mailer.sent[1].text
    assert created.invitation.token in mailer.sent[1].text


@pytest.mark.asyncio
async def test_resend_rejects_revoked():
    org = make_org(is_personal=False)
    owner = make_user()
    service, mailer = _team(org)
    created = await service.invite(
        org.id, owner, MembershipRole.OWNER, "carlos@empresa.com", MembershipRole.MEMBER
    )
    await service.revoke(org.id, MembershipRole.OWNER, created.invitation.id)

    with pytest.raises(DomainError, match="pendientes"):
        await service.resend(org.id, owner, MembershipRole.OWNER, created.invitation.id)
    assert len(mailer.sent) == 1


@pytest.mark.asyncio
async def test_resend_unknown_invitation():
    org = make_org(is_personal=False)
    owner = make_user()
    service, _ = _team(org)
    with pytest.raises(NotFoundError):
        await service.resend(org.id, owner, MembershipRole.OWNER, uuid4())


@pytest.mark.asyncio
async def test_snapshot_includes_last_seen_and_pending_invites():
    org = make_org(is_personal=False)
    owner = make_user(email="owner@empresa.com", full_name="Owner")
    member = make_user(email="ana@empresa.com", full_name="Ana")
    seen_at = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)
    service, _ = _team(org)
    owner_membership = make_membership(owner, org.id, MembershipRole.OWNER)
    owner_membership.last_seen_at = seen_at
    service.memberships.items = [
        owner_membership,
        make_membership(member, org.id, MembershipRole.MEMBER),
    ]
    await service.invite(org.id, owner, MembershipRole.OWNER, "carlos@empresa.com", MembershipRole.MEMBER)

    snapshot = await service.snapshot(org.id, MembershipRole.OWNER)

    by_email = {item.email: item for item in snapshot.members}
    assert by_email["owner@empresa.com"].last_seen_at == seen_at
    assert by_email["ana@empresa.com"].last_seen_at is None
    pending = [item for item in snapshot.invitations if item.status == InvitationStatus.PENDING]
    assert [item.email for item in pending] == ["carlos@empresa.com"]


@pytest.mark.asyncio
async def test_accept_adds_membership():
    org = make_org(is_personal=False)
    owner = make_user()
    invitee = make_user(email="carlos@empresa.com")
    service, _ = _team(org)
    created = await service.invite(
        org.id, owner, MembershipRole.OWNER, invitee.email, MembershipRole.MEMBER
    )

    result = await service.accept(created.invitation.token, invitee)

    assert result.organization.id == org.id
    assert created.invitation.status == InvitationStatus.ACCEPTED
    membership = await service.memberships.get(invitee.id, org.id)
    assert membership is not None
    assert membership.role == MembershipRole.MEMBER


@pytest.mark.asyncio
async def test_accept_is_idempotent_for_same_member():
    org = make_org(is_personal=False)
    owner = make_user()
    invitee = make_user(email="carlos@empresa.com")
    service, _ = _team(org)
    created = await service.invite(
        org.id, owner, MembershipRole.OWNER, invitee.email, MembershipRole.MEMBER
    )
    await service.accept(created.invitation.token, invitee)
    events_after_first = len(service.audit.events)

    result = await service.accept(created.invitation.token, invitee)

    assert result.organization.id == org.id
    assert result.role == MembershipRole.MEMBER
    assert len(service.audit.events) == events_after_first
    assert len([item for item in service.memberships.items if item.user_id == invitee.id]) == 1


@pytest.mark.asyncio
async def test_accept_rejects_wrong_email_after_accepted():
    org = make_org(is_personal=False)
    owner = make_user()
    invitee = make_user(email="carlos@empresa.com")
    other = make_user(email="otro@empresa.com")
    service, _ = _team(org)
    created = await service.invite(
        org.id, owner, MembershipRole.OWNER, invitee.email, MembershipRole.MEMBER
    )
    await service.accept(created.invitation.token, invitee)

    with pytest.raises(ForbiddenError, match="otro correo"):
        await service.accept(created.invitation.token, other)


@pytest.mark.asyncio
async def test_free_team_cannot_invite():
    org = make_org(is_personal=False, plan=PlanTier.FREE)
    owner = make_user()
    service, mailer = _team(org)

    with pytest.raises(DomainError, match="plan gratuito"):
        await service.invite(org.id, owner, MembershipRole.OWNER, "carlos@empresa.com", MembershipRole.MEMBER)
    assert mailer.sent == []


@pytest.mark.asyncio
async def test_team_plan_blocks_invite_at_seat_limit():
    org = make_org(is_personal=False, plan=PlanTier.TEAM)
    owner = make_user()
    service, _ = _team(org)
    service.memberships.items = [make_membership(owner, org.id, MembershipRole.OWNER)]
    for index in range(24):
        person = make_user(email=f"user{index:02d}@empresa.com")
        service.memberships.items.append(make_membership(person, org.id, MembershipRole.MEMBER))

    with pytest.raises(DomainError, match="25"):
        await service.invite(org.id, owner, MembershipRole.OWNER, "nuevo@empresa.com", MembershipRole.MEMBER)


@pytest.mark.asyncio
async def test_snapshot_exposes_seat_usage():
    org = make_org(is_personal=False, plan=PlanTier.TEAM)
    owner = make_user()
    service, _ = _team(org)
    service.memberships.items = [make_membership(owner, org.id, MembershipRole.OWNER)]

    snapshot = await service.snapshot(org.id, MembershipRole.OWNER)

    assert snapshot.can_invite is True
    assert snapshot.seat_limit == 25
    assert snapshot.seat_used == 1


@pytest.mark.asyncio
async def test_pending_invite_occupies_a_seat():
    org = make_org(is_personal=False, plan=PlanTier.TEAM)
    owner = make_user()
    service, _ = _team(org)
    service.memberships.items = [make_membership(owner, org.id, MembershipRole.OWNER)]
    for index in range(23):
        person = make_user(email=f"user{index:02d}@empresa.com")
        service.memberships.items.append(make_membership(person, org.id, MembershipRole.MEMBER))

    await service.invite(org.id, owner, MembershipRole.OWNER, "pendiente@empresa.com", MembershipRole.MEMBER)

    with pytest.raises(DomainError, match="25"):
        await service.invite(org.id, owner, MembershipRole.OWNER, "nuevo@empresa.com", MembershipRole.MEMBER)


@pytest.mark.asyncio
async def test_accept_blocked_when_seats_full():
    org = make_org(is_personal=False, plan=PlanTier.TEAM)
    owner = make_user()
    invitee = make_user(email="carlos@empresa.com")
    service, _ = _team(org)
    service.memberships.items = [make_membership(owner, org.id, MembershipRole.OWNER)]
    for index in range(23):
        person = make_user(email=f"user{index:02d}@empresa.com")
        service.memberships.items.append(make_membership(person, org.id, MembershipRole.MEMBER))

    created = await service.invite(
        org.id, owner, MembershipRole.OWNER, invitee.email, MembershipRole.MEMBER
    )
    extra = make_user(email="lleno@empresa.com")
    service.memberships.items.append(make_membership(extra, org.id, MembershipRole.MEMBER))

    with pytest.raises(DomainError, match="25"):
        await service.accept(created.invitation.token, invitee)

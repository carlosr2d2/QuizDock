from uuid import uuid4

import pytest

from app.models import MembershipRole
from app.models.exam import ExamStatus
from app.models.group import Group, GroupMember
from app.schemas.content import ExamAssignRequest
from app.services.billing import BillingService
from app.services.errors import ConflictError, DomainError, ForbiddenError, NotFoundError
from app.services.generation import ExamService
from app.services.team import TeamService
from tests.fakes import (
    FakeDocumentRepo,
    FakeExamRepo,
    FakeGroupRepo,
    FakeInvitationRepo,
    FakeMembershipRepo,
    FakeOrgRepo,
    FakeSession,
    FakeTxRepo,
    FakeUserRepo,
    make_exam,
    make_membership,
    make_org,
    make_user,
)


def _team(org) -> TeamService:
    service = TeamService(FakeSession())
    service.orgs = FakeOrgRepo()
    service.orgs.by_id[org.id] = org
    service.orgs.slugs.add(org.slug)
    service.users = FakeUserRepo()
    service.memberships = FakeMembershipRepo()
    service.groups = FakeGroupRepo()
    service.invitations = FakeInvitationRepo()
    return service


def _exams(org) -> ExamService:
    session = FakeSession()
    service = ExamService(session)
    service.orgs = FakeOrgRepo()
    service.orgs.by_id[org.id] = org
    service.orgs.slugs.add(org.slug)
    service.documents = FakeDocumentRepo()
    service.repo = FakeExamRepo()
    service.memberships = FakeMembershipRepo()
    service.groups = FakeGroupRepo()
    service.billing = BillingService(session)
    service.billing.orgs = service.orgs
    service.billing.txs = FakeTxRepo()
    return service


@pytest.mark.asyncio
async def test_create_group_in_team_workspace():
    org = make_org(is_personal=False, slug="demo-empresa")
    owner = make_user()
    service = _team(org)
    service.memberships.items = [make_membership(owner, org.id, MembershipRole.OWNER)]

    group = await service.create_group(org.id, owner.id, MembershipRole.OWNER, "Turno mañana")

    assert group.name == "Turno mañana"
    assert group.member_count == 0
    assert group.organization_id == org.id


@pytest.mark.asyncio
async def test_create_group_rejects_personal_workspace():
    org = make_org(is_personal=True)
    owner = make_user()
    service = _team(org)
    with pytest.raises(DomainError, match="personal"):
        await service.create_group(org.id, owner.id, MembershipRole.OWNER, "Grupo")


@pytest.mark.asyncio
async def test_member_cannot_create_group():
    org = make_org(is_personal=False)
    service = _team(org)
    with pytest.raises(ForbiddenError):
        await service.create_group(org.id, uuid4(), MembershipRole.MEMBER, "Grupo")


@pytest.mark.asyncio
async def test_duplicate_group_name_is_rejected():
    org = make_org(is_personal=False)
    owner = make_user()
    service = _team(org)
    await service.create_group(org.id, owner.id, MembershipRole.OWNER, "Turno mañana")
    with pytest.raises(ConflictError, match="nombre"):
        await service.create_group(org.id, owner.id, MembershipRole.OWNER, "Turno mañana")


@pytest.mark.asyncio
async def test_member_can_belong_to_several_groups():
    org = make_org(is_personal=False)
    owner = make_user()
    carlos = make_user(email="carlos@example.com", full_name="Carlos Gomez")
    service = _team(org)
    service.memberships.items = [
        make_membership(owner, org.id, MembershipRole.OWNER),
        make_membership(carlos, org.id, MembershipRole.MEMBER),
    ]
    morning = await service.create_group(org.id, owner.id, MembershipRole.OWNER, "Turno mañana")
    safety = await service.create_group(org.id, owner.id, MembershipRole.OWNER, "Seguridad")

    await service.add_group_members(org.id, MembershipRole.OWNER, morning.id, [carlos.id])
    await service.add_group_members(org.id, MembershipRole.OWNER, safety.id, [carlos.id])

    snapshot = await service.snapshot(org.id, MembershipRole.OWNER)
    names = {group.name: {member.user_id for member in group.members} for group in snapshot.groups}
    assert names["Turno mañana"] == {carlos.id}
    assert names["Seguridad"] == {carlos.id}


@pytest.mark.asyncio
async def test_cannot_add_user_outside_workspace_to_group():
    org = make_org(is_personal=False)
    owner = make_user()
    service = _team(org)
    service.memberships.items = [make_membership(owner, org.id, MembershipRole.OWNER)]
    group = await service.create_group(org.id, owner.id, MembershipRole.OWNER, "Turno")
    with pytest.raises(DomainError, match="no pertenecen"):
        await service.add_group_members(org.id, MembershipRole.OWNER, group.id, [uuid4()])


@pytest.mark.asyncio
async def test_set_group_members_replaces_the_roster():
    org = make_org(is_personal=False)
    owner = make_user()
    ana = make_user(email="ana@example.com", full_name="Ana")
    carlos = make_user(email="carlos@example.com", full_name="Carlos")
    service = _team(org)
    service.memberships.items = [
        make_membership(owner, org.id, MembershipRole.OWNER),
        make_membership(ana, org.id, MembershipRole.MEMBER),
        make_membership(carlos, org.id, MembershipRole.MEMBER),
    ]
    group = await service.create_group(org.id, owner.id, MembershipRole.OWNER, "Turno")
    await service.set_group_members(org.id, MembershipRole.OWNER, group.id, [ana.id, carlos.id])
    updated = await service.set_group_members(org.id, MembershipRole.OWNER, group.id, [ana.id])
    assert {member.user_id for member in updated.members} == {ana.id}


@pytest.mark.asyncio
async def test_assign_exam_to_group_covers_all_members():
    org = make_org(is_personal=False, slug="demo-empresa")
    owner = make_user()
    ana = make_user(email="ana@example.com", full_name="Ana")
    carlos = make_user(email="carlos@example.com", full_name="Carlos")
    exams = _exams(org)
    exams.memberships.items = [
        make_membership(owner, org.id, MembershipRole.OWNER),
        make_membership(ana, org.id, MembershipRole.MEMBER),
        make_membership(carlos, org.id, MembershipRole.MEMBER),
    ]
    group = Group(organization_id=org.id, name="Turno mañana", created_by_user_id=owner.id)
    await exams.groups.add(group)
    await exams.groups.add_member(
        GroupMember(organization_id=org.id, group_id=group.id, user_id=ana.id)
    )
    await exams.groups.add_member(
        GroupMember(organization_id=org.id, group_id=group.id, user_id=carlos.id)
    )
    exam = make_exam(org.id, owner.id, uuid4(), status=ExamStatus.READY)
    exams.repo.exams.append(exam)
    exams.repo.people = {owner.id: owner, ana.id: ana, carlos.id: carlos}

    roster = await exams.assign(
        exam.id,
        org.id,
        owner.id,
        MembershipRole.OWNER,
        ExamAssignRequest(group_ids=[group.id]),
    )

    assert {item.user_id for item in roster} == {ana.id, carlos.id}
    assert exams.repo.group_assignments[0].group_id == group.id


@pytest.mark.asyncio
async def test_assign_exam_to_individual_still_works():
    org = make_org(is_personal=False)
    owner = make_user()
    carlos = make_user(email="carlos@example.com", full_name="Carlos")
    exams = _exams(org)
    exams.memberships.items = [
        make_membership(owner, org.id, MembershipRole.OWNER),
        make_membership(carlos, org.id, MembershipRole.MEMBER),
    ]
    exam = make_exam(org.id, owner.id, uuid4(), status=ExamStatus.READY)
    exams.repo.exams.append(exam)
    exams.repo.people = {owner.id: owner, carlos.id: carlos}

    roster = await exams.assign(
        exam.id,
        org.id,
        owner.id,
        MembershipRole.OWNER,
        ExamAssignRequest(user_ids=[carlos.id]),
    )
    assert len(roster) == 1
    assert roster[0].user_id == carlos.id
    assert exams.repo.group_assignments == []


@pytest.mark.asyncio
async def test_overlapping_groups_do_not_duplicate_assignments():
    org = make_org(is_personal=False)
    owner = make_user()
    carlos = make_user(email="carlos@example.com", full_name="Carlos")
    exams = _exams(org)
    exams.memberships.items = [
        make_membership(owner, org.id, MembershipRole.OWNER),
        make_membership(carlos, org.id, MembershipRole.MEMBER),
    ]
    morning = Group(organization_id=org.id, name="Mañana", created_by_user_id=owner.id)
    safety = Group(organization_id=org.id, name="Seguridad", created_by_user_id=owner.id)
    await exams.groups.add(morning)
    await exams.groups.add(safety)
    await exams.groups.add_member(
        GroupMember(organization_id=org.id, group_id=morning.id, user_id=carlos.id)
    )
    await exams.groups.add_member(
        GroupMember(organization_id=org.id, group_id=safety.id, user_id=carlos.id)
    )
    exam = make_exam(org.id, owner.id, uuid4(), status=ExamStatus.READY)
    exams.repo.exams.append(exam)
    exams.repo.people = {owner.id: owner, carlos.id: carlos}

    roster = await exams.assign(
        exam.id,
        org.id,
        owner.id,
        MembershipRole.OWNER,
        ExamAssignRequest(group_ids=[morning.id, safety.id], user_ids=[carlos.id]),
    )
    assert len(roster) == 1
    assert roster[0].user_id == carlos.id
    assert {item.group_id for item in exams.repo.group_assignments} == {morning.id, safety.id}


@pytest.mark.asyncio
async def test_assign_empty_group_is_rejected():
    org = make_org(is_personal=False)
    owner = make_user()
    exams = _exams(org)
    exams.memberships.items = [make_membership(owner, org.id, MembershipRole.OWNER)]
    group = Group(organization_id=org.id, name="Vacío", created_by_user_id=owner.id)
    await exams.groups.add(group)
    exam = make_exam(org.id, owner.id, uuid4(), status=ExamStatus.READY)
    exams.repo.exams.append(exam)

    with pytest.raises(DomainError, match="no tiene integrantes"):
        await exams.assign(
            exam.id,
            org.id,
            owner.id,
            MembershipRole.OWNER,
            ExamAssignRequest(group_ids=[group.id]),
        )


@pytest.mark.asyncio
async def test_assign_unknown_group():
    org = make_org(is_personal=False)
    owner = make_user()
    exams = _exams(org)
    exams.memberships.items = [make_membership(owner, org.id, MembershipRole.OWNER)]
    exam = make_exam(org.id, owner.id, uuid4(), status=ExamStatus.READY)
    exams.repo.exams.append(exam)
    with pytest.raises(NotFoundError, match="Grupo"):
        await exams.assign(
            exam.id,
            org.id,
            owner.id,
            MembershipRole.OWNER,
            ExamAssignRequest(group_ids=[uuid4()]),
        )

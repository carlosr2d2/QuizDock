from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models import MembershipRole
from app.models.exam import AssignmentStatus, ExamAssignment, ExamAttempt, ExamStatus
from app.services.billing import BillingService
from app.services.errors import DomainError, ForbiddenError
from app.services.generation import ExamService
from tests.fakes import (
    FakeDocumentRepo,
    FakeExamRepo,
    FakeMembershipRepo,
    FakeOrgRepo,
    FakeSession,
    FakeTxRepo,
    FakeAuditService,
    make_exam,
    make_membership,
    make_org,
    make_user,
)


def _service(org) -> ExamService:
    session = FakeSession()
    service = ExamService(session)
    service.orgs = FakeOrgRepo()
    service.orgs.by_id[org.id] = org
    service.documents = FakeDocumentRepo()
    service.repo = FakeExamRepo()
    service.memberships = FakeMembershipRepo()
    service.billing = BillingService(session)
    service.billing.orgs = service.orgs
    service.billing.txs = FakeTxRepo()
    service.audit = FakeAuditService()
    return service


def _attempt(exam, user, org_id, score: float) -> ExamAttempt:
    now = datetime.now(timezone.utc)
    return ExamAttempt(
        id=uuid4(),
        exam_id=exam.id,
        user_id=user.id,
        organization_id=org_id,
        score=score,
        started_at=now,
        completed_at=now,
        answers={},
        created_at=now,
        updated_at=now,
    )


def _assignment(exam, user, org_id, *, completed: bool) -> ExamAssignment:
    now = datetime.now(timezone.utc)
    return ExamAssignment(
        id=uuid4(),
        organization_id=org_id,
        exam_id=exam.id,
        user_id=user.id,
        status=AssignmentStatus.COMPLETED if completed else AssignmentStatus.PENDING,
        completed_at=now if completed else None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_member_cannot_view_team_analytics():
    org = make_org(is_personal=False)
    service = _service(org)
    with pytest.raises(ForbiddenError, match="analíticas"):
        await service.team_analytics(org.id, MembershipRole.MEMBER)


@pytest.mark.asyncio
async def test_personal_workspace_has_no_team_analytics():
    org = make_org(is_personal=True)
    service = _service(org)
    with pytest.raises(DomainError, match="personal"):
        await service.team_analytics(org.id, MembershipRole.OWNER)


@pytest.mark.asyncio
async def test_owner_sees_workspace_kpis_members_and_exams():
    org = make_org(is_personal=False, slug="demo-empresa")
    owner = make_user(full_name="Demo Tester")
    carlos = make_user(email="carlos@example.com", full_name="Carlos Gomez")
    ana = make_user(email="ana@example.com", full_name="Ana")
    exam = make_exam(org.id, owner.id, uuid4(), status=ExamStatus.READY)
    exam.title = "Normativa interna"
    service = _service(org)
    service.memberships.items = [
        make_membership(owner, org.id, MembershipRole.OWNER),
        make_membership(carlos, org.id, MembershipRole.MEMBER),
        make_membership(ana, org.id, MembershipRole.MEMBER),
    ]
    service.repo.exams.append(exam)
    service.repo.people[carlos.id] = carlos
    service.repo.attempts.append(_attempt(exam, carlos, org.id, 87.5))
    service.repo.assignments.append(_assignment(exam, carlos, org.id, completed=True))
    service.repo.assignments.append(_assignment(exam, ana, org.id, completed=False))

    result = await service.team_analytics(org.id, MembershipRole.OWNER)

    assert result.member_count == 3
    assert result.assigned_count == 2
    assert result.completed_count == 1
    assert result.pending_count == 1
    assert result.completion_rate == 50.0
    assert result.average_score == 87.5
    assert result.attempt_count == 1
    by_email = {item.email: item for item in result.members}
    assert by_email["carlos@example.com"].exams_taken == 1
    assert by_email["carlos@example.com"].average_score == 87.5
    assert by_email["carlos@example.com"].assigned_pending_count == 0
    assert by_email["ana@example.com"].assigned_pending_count == 1
    assert by_email["ana@example.com"].exams_taken == 0
    assert result.members[0].email == "ana@example.com"
    assert result.exams[0].title == "Normativa interna"
    assert result.exams[0].assigned_count == 2
    assert result.exams[0].completed_count == 1
    assert result.exams[0].average_score == 87.5
    assert result.recent[0].full_name == "Carlos Gomez"
    assert result.recent[0].exam_title == "Normativa interna"


@pytest.mark.asyncio
async def test_auditor_can_view_team_analytics():
    org = make_org(is_personal=False)
    service = _service(org)
    service.memberships.items = [make_membership(make_user(), org.id, MembershipRole.AUDITOR)]
    result = await service.team_analytics(org.id, MembershipRole.AUDITOR)
    assert result.member_count == 1
    assert result.assigned_count == 0
    assert result.completion_rate is None
    assert result.average_score is None
    assert result.exams == []
    assert result.recent == []

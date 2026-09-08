from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models import MembershipRole
from app.models.exam import AssignmentStatus, ExamAssignment, ExamAttempt, ExamStatus
from app.services.errors import ForbiddenError, NotFoundError
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
from app.services.billing import BillingService


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


@pytest.mark.asyncio
async def test_member_cannot_view_another_member_progress():
    org = make_org(is_personal=False)
    owner = make_user()
    member = make_user(email="carlos@example.com", full_name="Carlos Gomez")
    other = make_user(email="ana@example.com", full_name="Ana")
    service = _service(org)
    service.memberships.items = [
        make_membership(owner, org.id, MembershipRole.OWNER),
        make_membership(member, org.id, MembershipRole.MEMBER),
        make_membership(other, org.id, MembershipRole.MEMBER),
    ]

    with pytest.raises(ForbiddenError, match="otro miembro"):
        await service.member_progress(org.id, member.id, MembershipRole.MEMBER, other.id)


@pytest.mark.asyncio
async def test_member_can_view_own_progress():
    org = make_org(is_personal=False)
    member = make_user(email="carlos@example.com", full_name="Carlos Gomez")
    service = _service(org)
    service.memberships.items = [make_membership(member, org.id, MembershipRole.MEMBER)]

    result = await service.member_progress(org.id, member.id, MembershipRole.MEMBER, member.id)
    assert result.user_id == member.id
    assert result.exams_taken == 0
    assert result.recent == []


@pytest.mark.asyncio
async def test_owner_sees_member_exam_summary():
    org = make_org(is_personal=False, slug="demo-empresa")
    owner = make_user()
    member = make_user(email="carlos@example.com", full_name="Carlos Gomez")
    exam = make_exam(org.id, owner.id, uuid4(), status=ExamStatus.READY)
    exam.title = "Normativa interna"
    now = datetime.now(timezone.utc)
    attempt = ExamAttempt(
        id=uuid4(),
        exam_id=exam.id,
        user_id=member.id,
        organization_id=org.id,
        score=87.5,
        started_at=now,
        completed_at=now,
        answers={},
        created_at=now,
        updated_at=now,
    )
    assignment = ExamAssignment(
        id=uuid4(),
        organization_id=org.id,
        exam_id=exam.id,
        user_id=member.id,
        status=AssignmentStatus.COMPLETED,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )
    service = _service(org)
    service.memberships.items = [
        make_membership(owner, org.id, MembershipRole.OWNER),
        make_membership(member, org.id, MembershipRole.MEMBER),
    ]
    service.repo.exams.append(exam)
    service.repo.attempts.append(attempt)
    service.repo.assignments.append(assignment)

    result = await service.member_progress(org.id, owner.id, MembershipRole.OWNER, member.id)

    assert result.full_name == "Carlos Gomez"
    assert result.exams_taken == 1
    assert result.attempt_count == 1
    assert result.average_score == 87.5
    assert result.last_score == 87.5
    assert result.assigned_count == 1
    assert result.assigned_pending_count == 0
    assert result.recent[0].exam_title == "Normativa interna"
    assert result.assignments[0].status == "completed"
    assert result.assignments[0].last_score == 87.5
    assert result.assignments[0].last_attempt_id == attempt.id


@pytest.mark.asyncio
async def test_member_progress_unknown_user():
    org = make_org(is_personal=False)
    owner = make_user()
    service = _service(org)
    service.memberships.items = [make_membership(owner, org.id, MembershipRole.OWNER)]
    with pytest.raises(NotFoundError):
        await service.member_progress(org.id, owner.id, MembershipRole.OWNER, uuid4())

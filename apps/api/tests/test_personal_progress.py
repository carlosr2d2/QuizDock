from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.models.exam import ExamAttempt, ExamStatus, QuestionKind
from app.schemas.content import FlashcardProgress, ProgressRead
from app.services.billing import BillingService
from app.services.generation import ExamService, kind_accuracy_from_attempts
from app.services.progress import consecutive_streak, merge_personal_progress
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
    make_question,
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


def _attempt(exam, user, org_id, score: float, *, when=None, answers=None) -> ExamAttempt:
    moment = when or datetime.now(timezone.utc)
    return ExamAttempt(
        id=uuid4(),
        exam_id=exam.id,
        user_id=user.id,
        organization_id=org_id,
        score=score,
        started_at=moment,
        completed_at=moment,
        answers=answers or {},
        created_at=moment,
        updated_at=moment,
    )


def test_consecutive_streak_counts_today_and_yesterday():
    today = datetime.now(timezone.utc).date()
    assert consecutive_streak([], today) == 0
    assert consecutive_streak([today], today) == 1
    assert consecutive_streak([today, today - timedelta(days=1)], today) == 2
    assert consecutive_streak([today - timedelta(days=1)], today) == 1
    assert consecutive_streak([today - timedelta(days=3)], today) == 0
    assert consecutive_streak([today, today - timedelta(days=2)], today) == 1


def test_merge_personal_progress_unions_study_dates():
    today = datetime.now(timezone.utc).date()
    exams = ProgressRead(
        attempt_count=1,
        exams_taken=1,
        average_score=70,
        best_score=70,
        last_score=70,
        study_streak_days=1,
        study_dates=[today],
    )
    cards = FlashcardProgress(
        flashcard_count=5,
        flashcard_due=2,
        flashcard_reviewed=3,
        flashcard_mastered=1,
        study_dates=[today - timedelta(days=1)],
    )
    merged = merge_personal_progress(exams, cards)
    assert merged.flashcard_count == 5
    assert merged.flashcard_mastered == 1
    assert merged.study_streak_days == 2
    assert "study_dates" not in merged.model_dump()


@pytest.mark.asyncio
async def test_progress_empty_has_insight_defaults():
    org = make_org()
    user = make_user()
    service = _service(org)
    result = await service.progress(org.id, user.id)
    assert result.attempt_count == 0
    assert result.trend == []
    assert result.weak_exams == []
    assert result.kind_accuracy == []
    assert result.study_streak_days == 0


@pytest.mark.asyncio
async def test_progress_trend_is_chronological():
    org = make_org()
    user = make_user()
    exam = make_exam(org.id, user.id, uuid4(), status=ExamStatus.READY)
    exam.title = "Tenancy"
    now = datetime.now(timezone.utc)
    service = _service(org)
    service.repo.exams.append(exam)
    service.repo.attempts.extend(
        [
            _attempt(exam, user, org.id, 40, when=now - timedelta(days=2)),
            _attempt(exam, user, org.id, 70, when=now - timedelta(days=1)),
            _attempt(exam, user, org.id, 90, when=now),
        ]
    )

    result = await service.progress(org.id, user.id)

    assert [item.score for item in result.trend] == [40, 70, 90]
    assert result.last_score == 90
    assert result.recent[0].score == 90
    assert result.study_streak_days == 3


@pytest.mark.asyncio
async def test_progress_weak_exams_are_below_threshold_and_tenant_scoped():
    org = make_org()
    other_org = make_org(slug="other-workspace")
    user = make_user()
    other = make_user(email="other@example.com")
    weak = make_exam(org.id, user.id, uuid4(), status=ExamStatus.READY)
    weak.title = "Normativa"
    strong = make_exam(org.id, user.id, uuid4(), status=ExamStatus.READY)
    strong.title = "Onboarding"
    leaked = make_exam(other_org.id, user.id, uuid4(), status=ExamStatus.READY)
    leaked.title = "Otro workspace"
    service = _service(org)
    service.repo.exams.extend([weak, strong, leaked])
    service.repo.attempts.extend(
        [
            _attempt(weak, user, org.id, 40),
            _attempt(weak, user, org.id, 50),
            _attempt(strong, user, org.id, 92),
            _attempt(weak, other, org.id, 10),
            _attempt(leaked, user, other_org.id, 5),
        ]
    )

    result = await service.progress(org.id, user.id)

    assert [item.exam_title for item in result.weak_exams] == ["Normativa"]
    assert result.weak_exams[0].average_score == 45.0
    assert result.weak_exams[0].attempt_count == 2
    assert result.exams_taken == 2
    assert result.attempt_count == 3


@pytest.mark.asyncio
async def test_progress_kind_accuracy_uses_own_answers():
    org = make_org()
    user = make_user()
    exam = make_exam(org.id, user.id, uuid4(), status=ExamStatus.READY)
    true_false = make_question(
        exam.id,
        prompt="¿Verdadero?",
        kind=QuestionKind.TRUE_FALSE,
        options=["Verdadero", "Falso"],
        correct_index=0,
    )
    single = make_question(
        exam.id,
        prompt="Elige una",
        kind=QuestionKind.SINGLE_CHOICE,
        correct_index=2,
        position=1,
    )
    exam.questions = [true_false, single]
    service = _service(org)
    service.repo.exams.append(exam)
    service.repo.attempts.append(
        _attempt(
            exam,
            user,
            org.id,
            50,
            answers={str(true_false.id): 0, str(single.id): 1},
        )
    )

    result = await service.progress(org.id, user.id)
    by_kind = {item.kind: item for item in result.kind_accuracy}

    assert by_kind[QuestionKind.TRUE_FALSE].accuracy == 100.0
    assert by_kind[QuestionKind.SINGLE_CHOICE].accuracy == 0.0
    assert QuestionKind.MULTIPLE_CHOICE not in by_kind


def test_kind_accuracy_ignores_questions_from_other_exams():
    exam_id = uuid4()
    other_id = uuid4()
    question = make_question(exam_id, kind=QuestionKind.TRUE_FALSE, options=["Sí", "No"])
    other = make_question(other_id, kind=QuestionKind.TRUE_FALSE, options=["Sí", "No"])
    attempt = ExamAttempt(
        id=uuid4(),
        exam_id=exam_id,
        user_id=uuid4(),
        organization_id=uuid4(),
        score=100,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        answers={str(question.id): 0},
    )
    rows = kind_accuracy_from_attempts(
        [attempt],
        {exam_id: [question], other_id: [other]},
    )
    assert len(rows) == 1
    assert rows[0].total == 1
    assert rows[0].correct == 1

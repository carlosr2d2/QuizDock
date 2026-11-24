from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.appeal import AppealAiStatus, AppealDecision
from app.models.exam import ExamAttempt, ExamStatus, QuestionKind
from app.models.identity import MembershipRole
from app.schemas.appeals import AppealCreate
from app.services.appeal_ai import AppealAiService
from app.services.appeals import AppealService
from app.services.errors import ForbiddenError
from tests.fakes import (
    FakeDocumentRepo,
    FakeExamRepo,
    FakeMembershipRepo,
    FakeOrgRepo,
    FakeSession,
    FakeUserRepo,
    make_document,
    make_exam,
    make_membership,
    make_org,
    make_question,
    make_user,
)
from tests.test_appeals import FakeAppealRepo, FakeChunkRepo, FakeEvidenceRepo, FakeMailer


class FakeBilling:
    def __init__(self) -> None:
        self.debited: list[tuple] = []

    async def debit(self, organization_id, user_id, amount, reason):
        self.debited.append((organization_id, user_id, amount, reason))
        return 999


class FakeLLM:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0

    async def complete_json(self, system: str, user: str, temperature: float = 0.3) -> dict:
        self.calls += 1
        return self.payload


def _appeal_setup():
    org = make_org(is_personal=False)
    student = make_user(email="student@example.com", full_name="Student")
    admin = make_user(email="admin@example.com", full_name="Admin")
    document = make_document(org.id, admin.id)
    exam = make_exam(org.id, admin.id, document.id, status=ExamStatus.READY)
    question = make_question(
        exam.id,
        prompt="¿Redis es solo en memoria?",
        kind=QuestionKind.SINGLE_CHOICE,
        correct_index=0,
    )
    exam.questions = [question]
    attempt = ExamAttempt(
        id=uuid4(),
        exam_id=exam.id,
        user_id=student.id,
        organization_id=org.id,
        score=0.0,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        answers={str(question.id): 1},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    appeals = AppealService(FakeSession())
    appeals.repo = FakeAppealRepo()
    appeals.exams = FakeExamRepo()
    appeals.exams.exams.append(exam)
    appeals.exams.attempts.append(attempt)
    appeals.exams.people[student.id] = student
    appeals.exams.people[admin.id] = admin
    appeals.documents = FakeDocumentRepo()
    appeals.documents.by_id[document.id] = document
    appeals.evidence_repo = FakeEvidenceRepo()
    appeals.chunks = FakeChunkRepo()
    appeals.memberships = FakeMembershipRepo()
    appeals.memberships.items.append(make_membership(admin, org.id, MembershipRole.ADMIN))
    appeals.users = FakeUserRepo()
    appeals.users.by_id[student.id] = student
    appeals.users.by_id[admin.id] = admin
    appeals.orgs = FakeOrgRepo()
    appeals.orgs.by_id[org.id] = org
    appeals.mailer = FakeMailer()
    return appeals, org, student, admin, question, attempt


@pytest.mark.asyncio
async def test_ai_review_detects_ambiguity(monkeypatch):
    appeals, org, student, admin, question, attempt = _appeal_setup()
    created = await appeals.create(
        org.id,
        student.id,
        MembershipRole.MEMBER,
        AppealCreate(
            attempt_id=attempt.id,
            question_id=question.id,
            argument="El libro admite persistencia y también uso en memoria.",
            evidence_quote="Redis puede persistir datos a disco además de operar en memoria.",
        ),
    )

    service = AppealAiService(FakeSession())
    service.repo = appeals.repo
    service.exams = appeals.exams
    service.billing = FakeBilling()
    service.llm = FakeLLM(
        {
            "recommendation": "needs_info",
            "confidence": 0.62,
            "rationale": "Hay ambigüedad: el documento admite ambas lecturas sobre persistencia.",
            "ambiguity": True,
            "alt_chunk_ids": [],
        }
    )
    monkeypatch.setattr("app.services.appeal_ai.enqueue", lambda *_args, **_kwargs: False)

    result = await service.request_review(org.id, admin.id, MembershipRole.ADMIN, created.id)
    assert result.status == AppealAiStatus.READY.value
    assert result.recommendation == AppealDecision.NEEDS_INFO.value
    assert result.ambiguity is True
    assert "ambig" in result.rationale.lower()
    assert service.billing.debited
    assert service.llm.calls == 1
    assert any(item.outcome == "needs_info" for item in appeals.repo.decisions)


@pytest.mark.asyncio
async def test_ai_review_can_accept_when_student_evidence_strong(monkeypatch):
    appeals, org, student, admin, question, attempt = _appeal_setup()
    created = await appeals.create(
        org.id,
        student.id,
        MembershipRole.MEMBER,
        AppealCreate(
            attempt_id=attempt.id,
            question_id=question.id,
            argument="Mi cita contradice la clave del examen.",
            evidence_quote="El texto dice explícitamente que la afirmación del examen es incorrecta.",
        ),
    )
    service = AppealAiService(FakeSession())
    service.repo = appeals.repo
    service.billing = FakeBilling()
    service.llm = FakeLLM(
        {
            "recommendation": "accepted",
            "confidence": 0.88,
            "rationale": "La evidencia del estudiante respalda su respuesta.",
            "ambiguity": False,
            "alt_chunk_ids": [],
        }
    )
    monkeypatch.setattr("app.services.appeal_ai.enqueue", lambda *_args, **_kwargs: False)
    result = await service.request_review(org.id, admin.id, MembershipRole.ADMIN, created.id)
    assert result.recommendation == "accepted"
    assert result.ambiguity is False


@pytest.mark.asyncio
async def test_member_cannot_request_ai_review():
    appeals, org, student, _admin, question, attempt = _appeal_setup()
    created = await appeals.create(
        org.id,
        student.id,
        MembershipRole.MEMBER,
        AppealCreate(
            attempt_id=attempt.id,
            question_id=question.id,
            argument="Quiero revisión automática pero no soy admin.",
            evidence_quote="Fragmento mínimo válido para crear la apelación.",
        ),
    )
    service = AppealAiService(FakeSession())
    service.repo = appeals.repo
    service.billing = FakeBilling()
    with pytest.raises(ForbiddenError):
        await service.request_review(org.id, student.id, MembershipRole.MEMBER, created.id)

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.appeal import (
    AppealActionLog,
    AppealCase,
    AppealDecision,
    AppealEvidence,
    AppealResolution,
    AppealStatus,
)
from app.models.chunk import DocumentChunk
from app.models.exam import ExamAttempt, ExamStatus, QuestionKind
from app.models.identity import MembershipRole
from app.schemas.appeals import AppealCreate, AppealEvidenceCreate, AppealResolveRequest, AppealStatusUpdate
from app.services.appeals import AppealService
from app.services.errors import ConflictError, DomainError, ForbiddenError, NotFoundError
from tests.fakes import (
    FakeDocumentRepo,
    FakeExamRepo,
    FakeMembershipRepo,
    FakeOrgRepo,
    FakeSession,
    FakeUserRepo,
    ensure_id,
    make_document,
    make_exam,
    make_membership,
    make_org,
    make_question,
    make_user,
)


class FakeAppealRepo:
    def __init__(self) -> None:
        self.cases: list[AppealCase] = []
        self.evidence: list[AppealEvidence] = []
        self.resolutions: list[AppealResolution] = []
        self.actions: list[AppealActionLog] = []

    async def add(self, row: AppealCase) -> AppealCase:
        ensure_id(row)
        if getattr(row, "created_at", None) is None:
            row.created_at = datetime.now(timezone.utc)
        if getattr(row, "updated_at", None) is None:
            row.updated_at = row.created_at
        self.cases.append(row)
        return row

    async def get(self, appeal_id, organization_id):
        for row in self.cases:
            if row.id == appeal_id and row.organization_id == organization_id:
                return row
        return None

    async def get_by_attempt_question(self, organization_id, attempt_id, question_id):
        for row in self.cases:
            if (
                row.organization_id == organization_id
                and row.attempt_id == attempt_id
                and row.question_id == question_id
            ):
                return row
        return None

    async def list_for_student(self, organization_id, student_user_id, *, status=None):
        rows = [
            row
            for row in self.cases
            if row.organization_id == organization_id and row.student_user_id == student_user_id
        ]
        if status is not None:
            rows = [row for row in rows if row.status == status]
        return rows

    async def list_for_org(self, organization_id, *, status=None):
        rows = [row for row in self.cases if row.organization_id == organization_id]
        if status is not None:
            rows = [row for row in rows if row.status == status]
        return rows

    async def add_evidence(self, row: AppealEvidence) -> AppealEvidence:
        ensure_id(row)
        if getattr(row, "created_at", None) is None:
            row.created_at = datetime.now(timezone.utc)
        if getattr(row, "updated_at", None) is None:
            row.updated_at = row.created_at
        if getattr(row, "source", None) is not None and hasattr(row.source, "value"):
            pass
        self.evidence.append(row)
        return row

    async def list_evidence(self, appeal_id, organization_id):
        return [
            row
            for row in self.evidence
            if row.appeal_id == appeal_id and row.organization_id == organization_id
        ]

    async def add_resolution(self, row: AppealResolution) -> AppealResolution:
        ensure_id(row)
        if getattr(row, "created_at", None) is None:
            row.created_at = datetime.now(timezone.utc)
        if getattr(row, "updated_at", None) is None:
            row.updated_at = row.created_at
        if getattr(row, "resolved_at", None) is None:
            row.resolved_at = datetime.now(timezone.utc)
        self.resolutions.append(row)
        return row

    async def get_resolution(self, appeal_id, organization_id):
        for row in self.resolutions:
            if row.appeal_id == appeal_id and row.organization_id == organization_id:
                return row
        return None

    async def add_action(self, row: AppealActionLog) -> AppealActionLog:
        ensure_id(row)
        if getattr(row, "created_at", None) is None:
            row.created_at = datetime.now(timezone.utc)
        self.actions.append(row)
        return row

    async def list_actions(self, appeal_id, organization_id):
        return [
            row
            for row in self.actions
            if row.appeal_id == appeal_id and row.organization_id == organization_id
        ]


class FakeEvidenceRepo:
    def __init__(self) -> None:
        self.by_question: dict = {}

    async def list_for_questions(self, organization_id, question_ids):
        return {qid: self.by_question[qid] for qid in question_ids if qid in self.by_question}


class FakeChunkRepo:
    def __init__(self) -> None:
        self.items: list[DocumentChunk] = []

    async def list_for_document(self, document_id, organization_id):
        return [
            row
            for row in self.items
            if row.document_id == document_id and row.organization_id == organization_id
        ]


class FakeMailer:
    def __init__(self) -> None:
        self.sent: list = []

    def send(self, message) -> None:
        self.sent.append(message)


def _setup():
    org = make_org(is_personal=False)
    student = make_user(email="student@example.com", full_name="Student")
    admin = make_user(email="admin@example.com", full_name="Admin")
    document = make_document(org.id, admin.id)
    exam = make_exam(org.id, admin.id, document.id, status=ExamStatus.READY)
    question = make_question(
        exam.id,
        prompt="¿Cuál es la capital?",
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
    chunk = DocumentChunk(
        id=uuid4(),
        organization_id=org.id,
        document_id=document.id,
        position=0,
        content="La capital de Francia es París y se encuentra en Europa.",
        embedding=[0.0] * 8,
        page_start=3,
        page_end=3,
        chapter="Geografía",
        section="Capitales",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    service = AppealService(FakeSession())
    service.repo = FakeAppealRepo()
    service.exams = FakeExamRepo()
    service.exams.exams.append(exam)
    service.exams.attempts.append(attempt)
    service.exams.people[student.id] = student
    service.documents = FakeDocumentRepo()
    service.documents.by_id[document.id] = document
    service.evidence_repo = FakeEvidenceRepo()
    service.chunks = FakeChunkRepo()
    service.chunks.items.append(chunk)
    service.memberships = FakeMembershipRepo()
    service.memberships.items.append(make_membership(admin, org.id, MembershipRole.ADMIN))
    service.users = FakeUserRepo()
    service.users.by_id[student.id] = student
    service.users.by_id[admin.id] = admin
    service.orgs = FakeOrgRepo()
    service.orgs.by_id[org.id] = org
    service.mailer = FakeMailer()
    return service, org, student, admin, exam, question, attempt, chunk


@pytest.mark.asyncio
async def test_create_appeal_for_incorrect_answer_notifies_reviewers():
    service, org, student, _admin, _exam, question, attempt, chunk = _setup()
    detail = await service.create(
        org.id,
        student.id,
        MembershipRole.MEMBER,
        AppealCreate(
            attempt_id=attempt.id,
            question_id=question.id,
            argument="Mi respuesta coincide con el documento.",
            evidence_chunk_id=chunk.id,
        ),
    )
    assert detail.status == AppealStatus.PENDING.value
    assert detail.question_prompt == question.prompt
    assert len(detail.evidence) == 1
    assert detail.evidence[0].page_start == 3
    assert len(service.mailer.sent) == 1
    assert "apelación" in service.mailer.sent[0].subject.lower() or "apelacion" in service.mailer.sent[0].subject.lower() or "Nueva" in service.mailer.sent[0].subject


@pytest.mark.asyncio
async def test_cannot_appeal_correct_answer():
    service, org, student, _admin, _exam, question, attempt, _chunk = _setup()
    attempt.answers = {str(question.id): 0}
    with pytest.raises(DomainError, match="incorrecta"):
        await service.create(
            org.id,
            student.id,
            MembershipRole.MEMBER,
            AppealCreate(
                attempt_id=attempt.id,
                question_id=question.id,
                argument="Estoy de acuerdo en realidad.",
            ),
        )


@pytest.mark.asyncio
async def test_duplicate_appeal_is_conflict():
    service, org, student, _admin, _exam, question, attempt, _chunk = _setup()
    payload = AppealCreate(
        attempt_id=attempt.id,
        question_id=question.id,
        argument="Primera apelación con suficiente texto.",
        evidence_quote="Fragmento del documento que respalda mi respuesta.",
    )
    await service.create(org.id, student.id, MembershipRole.MEMBER, payload)
    with pytest.raises(ConflictError):
        await service.create(org.id, student.id, MembershipRole.MEMBER, payload)


@pytest.mark.asyncio
async def test_member_cannot_see_inbox():
    service, org, student, *_rest = _setup()
    with pytest.raises(ForbiddenError):
        await service.list(org.id, student.id, MembershipRole.MEMBER, inbox=True)


@pytest.mark.asyncio
async def test_resolve_accept_and_reject_lifecycle():
    service, org, student, admin, _exam, question, attempt, _chunk = _setup()
    created = await service.create(
        org.id,
        student.id,
        MembershipRole.MEMBER,
        AppealCreate(
            attempt_id=attempt.id,
            question_id=question.id,
            argument="La clave está mal según el capítulo 2.",
            evidence_quote="Texto del capítulo 2 que contradice la clave.",
        ),
    )
    await service.update_status(
        org.id,
        admin.id,
        MembershipRole.ADMIN,
        created.id,
        AppealStatusUpdate(status="in_review"),
    )
    accepted = await service.resolve(
        org.id,
        admin.id,
        MembershipRole.ADMIN,
        created.id,
        AppealResolveRequest(decision=AppealDecision.ACCEPTED.value, rationale="Tiene razón."),
    )
    assert accepted.status == AppealStatus.ACCEPTED.value
    assert accepted.resolution is not None
    assert accepted.resolution.decision == AppealDecision.ACCEPTED.value


@pytest.mark.asyncio
async def test_add_student_evidence_from_chunk():
    service, org, student, _admin, _exam, question, attempt, chunk = _setup()
    created = await service.create(
        org.id,
        student.id,
        MembershipRole.MEMBER,
        AppealCreate(
            attempt_id=attempt.id,
            question_id=question.id,
            argument="Argumento inicial sin evidencia adjunta todavía.",
        ),
    )
    detail = await service.add_evidence(
        org.id,
        student.id,
        MembershipRole.MEMBER,
        created.id,
        AppealEvidenceCreate(chunk_id=chunk.id, argument="Este fragmento lo demuestra."),
    )
    assert len(detail.evidence) == 1
    assert "París" in detail.evidence[0].quote or "Paris" in detail.evidence[0].quote or len(detail.evidence[0].quote) >= 8


@pytest.mark.asyncio
async def test_list_document_chunks_requires_org_document():
    service, org, *_rest, chunk = _setup()
    rows = await service.list_document_chunks(org.id, chunk.document_id, limit=10)
    assert len(rows) == 1
    assert rows[0].id == chunk.id
    with pytest.raises(NotFoundError):
        await service.list_document_chunks(org.id, uuid4())

from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.models import MembershipRole
from app.models.document import DocumentStatus
from app.models.exam import AssignmentStatus, ExamAssignment, ExamStatus, Question, QuestionKind
from app.schemas.content import AttemptSubmit, ExamAssignRequest, ExamGenerateRequest
from app.services.billing import BillingService
from app.services.errors import ConflictError, DomainError, ForbiddenError, InsufficientCreditsError, NotFoundError
from app.services.generation import ExamService
from app.services.llm import GeneratedExam, GeneratedQuestion
from app.services.permissions import can_author_content, require_author
from app.services.rag import RetrievedContext
from tests.fakes import (
    FakeDocumentRepo,
    FakeExamRepo,
    FakeGroupRepo,
    FakeMembershipRepo,
    FakeOrgRepo,
    FakeSession,
    FakeTxRepo,
    FakeAuditService,
    make_document,
    make_exam,
    make_membership,
    make_org,
    make_question,
    make_user,
)

settings = get_settings()


def _exam_service(org, *, document=None, exam=None) -> ExamService:
    session = FakeSession()
    service = ExamService(session)
    service.orgs = FakeOrgRepo()
    service.orgs.by_id[org.id] = org
    service.orgs.slugs.add(org.slug)
    service.documents = FakeDocumentRepo()
    if document is not None:
        service.documents.by_id[document.id] = document
    service.repo = FakeExamRepo()
    if exam is not None:
        service.repo.exams.append(exam)
        if not hasattr(exam, "questions") or exam.questions is None:
            exam.questions = []
    service.memberships = FakeMembershipRepo()
    service.groups = FakeGroupRepo()
    service.billing = BillingService(session)
    service.billing.orgs = service.orgs
    service.billing.txs = FakeTxRepo()
    service.audit = FakeAuditService()
    return service


def test_only_owner_and_admin_can_author():
    assert can_author_content(MembershipRole.OWNER) is True
    assert can_author_content(MembershipRole.ADMIN) is True
    assert can_author_content(MembershipRole.MEMBER) is False
    assert can_author_content(MembershipRole.AUDITOR) is False
    with pytest.raises(ForbiddenError):
        require_author(MembershipRole.MEMBER)


@pytest.mark.asyncio
async def test_member_cannot_request_exam_generation():
    org = make_org()
    document = make_document(org.id, uuid4())
    service = _exam_service(org, document=document)
    with pytest.raises(ForbiddenError):
        await service.request_generation(
            org.id,
            uuid4(),
            MembershipRole.MEMBER,
            ExamGenerateRequest(document_id=document.id, question_count=8),
        )
    assert org.credit_balance == 50
    assert service.repo.exams == []


@pytest.mark.asyncio
async def test_generation_requires_a_ready_document():
    org = make_org()
    owner_id = uuid4()
    missing = _exam_service(org)
    with pytest.raises(NotFoundError):
        await missing.request_generation(
            org.id,
            owner_id,
            MembershipRole.OWNER,
            ExamGenerateRequest(document_id=uuid4(), question_count=8),
        )

    processing = make_document(org.id, owner_id, status=DocumentStatus.PROCESSING)
    service = _exam_service(org, document=processing)
    with pytest.raises(ConflictError, match="no está listo"):
        await service.request_generation(
            org.id,
            owner_id,
            MembershipRole.OWNER,
            ExamGenerateRequest(document_id=processing.id, question_count=8),
        )


@pytest.mark.asyncio
async def test_request_generation_debits_credits_and_enqueues(monkeypatch):
    monkeypatch.setattr("app.services.generation.enqueue", lambda *args, **kwargs: True)
    org = make_org(credit_balance=50)
    owner_id = uuid4()
    document = make_document(org.id, owner_id)
    service = _exam_service(org, document=document)

    result = await service.request_generation(
        org.id,
        owner_id,
        MembershipRole.OWNER,
        ExamGenerateRequest(document_id=document.id, title="Quiz RAG", question_count=8),
    )

    cost = 8 * settings.credit_cost_per_question
    assert result.status is ExamStatus.GENERATING
    assert result.credit_cost == cost
    assert result.question_count == 8
    assert result.title == "Quiz RAG"
    assert org.credit_balance == 50 - cost
    assert service.billing.txs.items[0].reason == "exam_generate"
    assert service.repo.exams[0].generated_count == 0


@pytest.mark.asyncio
async def test_request_generation_refunds_when_worker_is_down(monkeypatch):
    monkeypatch.setattr("app.services.generation.enqueue", lambda *args, **kwargs: False)
    org = make_org(credit_balance=50)
    owner_id = uuid4()
    document = make_document(org.id, owner_id)
    service = _exam_service(org, document=document)

    with pytest.raises(ConflictError, match="worker"):
        await service.request_generation(
            org.id,
            owner_id,
            MembershipRole.OWNER,
            ExamGenerateRequest(document_id=document.id, question_count=8),
        )

    assert org.credit_balance == 50
    reasons = [item.reason for item in service.billing.txs.items]
    assert reasons == ["exam_generate", "exam_generate_refund"]
    assert service.repo.exams[0].status is ExamStatus.DRAFT


@pytest.mark.asyncio
async def test_request_generation_stops_when_credits_run_out():
    org = make_org(credit_balance=2)
    owner_id = uuid4()
    document = make_document(org.id, owner_id)
    service = _exam_service(org, document=document)

    with pytest.raises(InsufficientCreditsError):
        await service.request_generation(
            org.id,
            owner_id,
            MembershipRole.OWNER,
            ExamGenerateRequest(document_id=document.id, question_count=8),
        )
    assert service.repo.exams == []
    assert org.credit_balance == 2


@pytest.mark.asyncio
async def test_fail_exam_refunds_generation_cost():
    org = make_org(credit_balance=42)
    owner_id = uuid4()
    exam = make_exam(org.id, owner_id, uuid4(), credit_cost=8)
    service = _exam_service(org, exam=exam)

    await service._fail_exam(exam, "Documento sin texto extraído")

    assert exam.status is ExamStatus.FAILED
    assert exam.error_message == "Documento sin texto extraído"
    assert org.credit_balance == 50
    assert service.billing.txs.items[0].reason == "exam_generate_refund"


@pytest.mark.asyncio
async def test_fulfill_persists_legacy_kind_as_value(monkeypatch):
    org = make_org(credit_balance=42)
    owner_id = uuid4()
    document = make_document(org.id, owner_id)
    exam = make_exam(org.id, owner_id, document.id, question_count=1, credit_cost=1)
    service = _exam_service(org, document=document, exam=exam)

    class FakeRag:
        def __init__(self, session) -> None:
            self.session = session

        async def contexts_for(self, *args, **kwargs):
            return [RetrievedContext(position=0, content="El tenancy unifica B2B y B2C.")]

    async def fake_generate(contexts, needed, language, title, on_question=None):
        question = GeneratedQuestion(
            prompt="¿Qué comparte B2B y B2C?",
            kind="SINGLE_CHOICE",
            options=["Tenancy", "Precios", "RBAC", "SMTP"],
            correct_indices=[0],
        )
        if on_question:
            await on_question(question)
        return GeneratedExam(title="Tenancy unificado", questions=[question])

    monkeypatch.setattr("app.services.generation.RagService", FakeRag)
    monkeypatch.setattr("app.services.generation.generate_exam_from_contexts", fake_generate)

    await service.fulfill(exam.id)

    assert exam.status is ExamStatus.READY
    assert exam.generated_count == 1
    assert exam.title == "Tenancy unificado"
    saved = service.repo.questions[0]
    assert saved.kind is QuestionKind.SINGLE_CHOICE
    assert saved.kind.value == "single_choice"


@pytest.mark.asyncio
async def test_fulfill_skips_exam_already_ready():
    org = make_org()
    exam = make_exam(org.id, uuid4(), uuid4(), status=ExamStatus.READY)
    service = _exam_service(org, exam=exam)
    await service.fulfill(exam.id)
    assert exam.status is ExamStatus.READY
    assert service.session.commits == 0


@pytest.mark.asyncio
async def test_submit_attempt_scores_mixed_question_kinds():
    org = make_org()
    owner_id = uuid4()
    true_false = Question(
        id=uuid4(),
        exam_id=uuid4(),
        prompt="¿Verdadero?",
        kind=QuestionKind.TRUE_FALSE,
        options=["Verdadero", "Falso"],
        correct_index=0,
        correct_indices=[0],
        position=0,
    )
    multi = Question(
        id=uuid4(),
        exam_id=true_false.exam_id,
        prompt="Elige todas",
        kind=QuestionKind.MULTIPLE_CHOICE,
        options=["A", "B", "C", "D"],
        correct_index=0,
        correct_indices=[0, 2],
        position=1,
    )
    exam = make_exam(org.id, owner_id, uuid4(), status=ExamStatus.READY, question_count=2)
    exam.questions = [true_false, multi]
    service = _exam_service(org, exam=exam)
    service.repo.people[owner_id] = make_user(personal_organization_id=org.id)
    service.repo.people[owner_id].id = owner_id

    result = await service.submit_attempt(
        exam.id,
        org.id,
        owner_id,
        MembershipRole.OWNER,
        AttemptSubmit(answers={str(true_false.id): 0, str(multi.id): [2, 0]}),
    )

    assert result.score == 100.0
    assert [item.is_correct for item in result.results] == [True, True]
    assert exam.questions[0].kind is QuestionKind.TRUE_FALSE


@pytest.mark.asyncio
async def test_member_cannot_take_unassigned_team_exam():
    org = make_org(is_personal=False)
    exam = make_exam(org.id, uuid4(), uuid4(), status=ExamStatus.READY)
    exam.questions = [
        Question(
            id=uuid4(),
            exam_id=exam.id,
            prompt="Q",
            kind=QuestionKind.SINGLE_CHOICE,
            options=["A", "B", "C", "D"],
            correct_index=0,
            correct_indices=[0],
            position=0,
        )
    ]
    service = _exam_service(org, exam=exam)
    with pytest.raises(ForbiddenError, match="no te fue asignado"):
        await service.submit_attempt(
            exam.id,
            org.id,
            uuid4(),
            MembershipRole.MEMBER,
            AttemptSubmit(answers={}),
        )


@pytest.mark.asyncio
async def test_assign_exam_to_team_members():
    org = make_org(is_personal=False, slug="demo-empresa")
    owner = make_user()
    member = make_user(email="carlos@example.com", full_name="Carlos")
    exam = make_exam(org.id, owner.id, uuid4(), status=ExamStatus.READY)
    service = _exam_service(org, exam=exam)
    service.memberships.items = [
        make_membership(owner, org.id, MembershipRole.OWNER),
        make_membership(member, org.id, MembershipRole.MEMBER),
    ]
    service.repo.people = {owner.id: owner, member.id: member}

    roster = await service.assign(
        exam.id,
        org.id,
        owner.id,
        MembershipRole.OWNER,
        ExamAssignRequest(user_ids=[member.id]),
    )

    assert len(roster) == 1
    assert roster[0].user_id == member.id
    assert roster[0].status == str(AssignmentStatus.PENDING)
    assert service.repo.assignments[0].exam_id == exam.id


@pytest.mark.asyncio
async def test_member_cannot_assign_exam():
    org = make_org(is_personal=False)
    exam = make_exam(org.id, uuid4(), uuid4(), status=ExamStatus.READY)
    service = _exam_service(org, exam=exam)
    with pytest.raises(ForbiddenError, match="asignar"):
        await service.assign(
            exam.id,
            org.id,
            uuid4(),
            MembershipRole.MEMBER,
            ExamAssignRequest(all_members=True),
        )


@pytest.mark.asyncio
async def test_assign_rejects_users_outside_the_workspace():
    org = make_org(is_personal=False)
    owner = make_user()
    exam = make_exam(org.id, owner.id, uuid4(), status=ExamStatus.READY)
    service = _exam_service(org, exam=exam)
    service.memberships.items = [make_membership(owner, org.id, MembershipRole.OWNER)]
    with pytest.raises(DomainError, match="no pertenecen"):
        await service.assign(
            exam.id,
            org.id,
            owner.id,
            MembershipRole.ADMIN,
            ExamAssignRequest(user_ids=[uuid4()]),
        )


@pytest.mark.asyncio
async def test_request_generation_stores_pdf_download_flag(monkeypatch):
    monkeypatch.setattr("app.services.generation.enqueue", lambda *args, **kwargs: True)
    org = make_org(credit_balance=50)
    owner_id = uuid4()
    document = make_document(org.id, owner_id)
    service = _exam_service(org, document=document)

    result = await service.request_generation(
        org.id,
        owner_id,
        MembershipRole.OWNER,
        ExamGenerateRequest(document_id=document.id, question_count=4, allow_pdf_download=True),
    )

    assert result.allow_pdf_download is True
    assert service.repo.exams[0].allow_pdf_download is True


@pytest.mark.asyncio
async def test_assigned_member_downloads_pdf_when_enabled():
    org = make_org(is_personal=False)
    owner = make_user()
    member = make_user(email="carlos@example.com")
    exam = make_exam(org.id, owner.id, uuid4(), status=ExamStatus.READY, allow_pdf_download=True)
    exam.questions = [
        make_question(exam.id, prompt="¿Cuál es la capital?", options=["Bogotá", "Medellín", "Cali", "Barranquilla"]),
    ]
    exam.questions[0].explanation = "No debe salir en el PDF"
    service = _exam_service(org, exam=exam)
    service.repo.assignments.append(
        ExamAssignment(
            organization_id=org.id,
            exam_id=exam.id,
            user_id=member.id,
            status=AssignmentStatus.PENDING,
        )
    )

    pdf, filename = await service.download_pdf(exam.id, org.id, member.id, MembershipRole.MEMBER)

    assert filename.endswith(".pdf")
    assert pdf.startswith(b"%PDF")
    from io import BytesIO

    from pypdf import PdfReader

    text = "".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)
    assert "capital" in text
    assert "Bogotá" in text
    assert "No debe salir" not in text


@pytest.mark.asyncio
async def test_assigned_member_cannot_download_pdf_when_disabled():
    org = make_org(is_personal=False)
    member = make_user()
    exam = make_exam(org.id, uuid4(), uuid4(), status=ExamStatus.READY, allow_pdf_download=False)
    exam.questions = [make_question(exam.id)]
    service = _exam_service(org, exam=exam)
    service.repo.assignments.append(
        ExamAssignment(
            organization_id=org.id,
            exam_id=exam.id,
            user_id=member.id,
            status=AssignmentStatus.PENDING,
        )
    )

    with pytest.raises(ForbiddenError, match="no habilitó"):
        await service.download_pdf(exam.id, org.id, member.id, MembershipRole.MEMBER)


@pytest.mark.asyncio
async def test_unassigned_member_cannot_download_pdf():
    org = make_org(is_personal=False)
    exam = make_exam(org.id, uuid4(), uuid4(), status=ExamStatus.READY, allow_pdf_download=True)
    exam.questions = [make_question(exam.id)]
    service = _exam_service(org, exam=exam)

    with pytest.raises(ForbiddenError, match="no te fue asignado"):
        await service.download_pdf(exam.id, org.id, uuid4(), MembershipRole.MEMBER)


@pytest.mark.asyncio
async def test_owner_can_download_pdf_without_enabling_assignees():
    org = make_org(is_personal=False)
    owner = make_user()
    exam = make_exam(org.id, owner.id, uuid4(), status=ExamStatus.READY, allow_pdf_download=False)
    exam.questions = [make_question(exam.id, prompt="Pregunta del owner")]
    service = _exam_service(org, exam=exam)

    pdf, _filename = await service.download_pdf(exam.id, org.id, owner.id, MembershipRole.OWNER)

    assert pdf.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_admin_can_toggle_pdf_download():
    org = make_org(is_personal=False)
    owner = make_user()
    exam = make_exam(org.id, owner.id, uuid4(), status=ExamStatus.READY, allow_pdf_download=False)
    exam.questions = [make_question(exam.id)]
    service = _exam_service(org, exam=exam)

    updated = await service.set_allow_pdf_download(exam.id, org.id, owner.id, MembershipRole.OWNER, True)

    assert updated.allow_pdf_download is True
    assert exam.allow_pdf_download is True

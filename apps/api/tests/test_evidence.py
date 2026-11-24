from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.chunk import DocumentChunk
from app.models.evidence import AnswerReference, EvidenceSource, QuestionEvidence
from app.models.exam import ExamAttempt, ExamStatus, Question, QuestionKind
from app.services.embeddings import hashed_embedding
from app.services.evidence import EvidenceService
from tests.fakes import FakeSession, ensure_id, make_document, make_exam, make_org


class FakeEvidenceRepo:
    def __init__(self) -> None:
        self.evidence: list[QuestionEvidence] = []
        self.references: list[AnswerReference] = []

    async def add_evidence(self, row: QuestionEvidence) -> QuestionEvidence:
        ensure_id(row)
        if getattr(row, "generated_at", None) is None:
            row.generated_at = datetime.now(timezone.utc)
        self.evidence.append(row)
        return row

    async def add_references(self, rows: list[AnswerReference]) -> None:
        for row in rows:
            ensure_id(row)
            if getattr(row, "generated_at", None) is None:
                row.generated_at = datetime.now(timezone.utc)
            self.references.append(row)

    async def list_for_questions(self, organization_id, question_ids):
        mapping = {}
        for row in self.evidence:
            if row.organization_id == organization_id and row.question_id in question_ids:
                mapping.setdefault(row.question_id, row)
        return mapping

    async def list_for_attempt(self, organization_id, attempt_id):
        return {
            row.question_id: row
            for row in self.references
            if row.organization_id == organization_id and row.attempt_id == attempt_id
        }


class FakeChunkRepo:
    def __init__(self, rows: list[DocumentChunk] | None = None) -> None:
        self.rows = list(rows or [])

    async def get_by_position(self, document_id, organization_id, position: int):
        for row in self.rows:
            if (
                row.document_id == document_id
                and row.organization_id == organization_id
                and row.position == position
            ):
                return row
        return None


@pytest.mark.asyncio
async def test_create_from_generation_persists_verified_quote():
    org = make_org()
    document = make_document(org.id, uuid4())
    question = Question(
        id=uuid4(),
        exam_id=uuid4(),
        prompt="¿Qué garantiza TCP?",
        kind=QuestionKind.SINGLE_CHOICE,
        options=["Entrega confiable", "Broadcast", "Nada", "DNS"],
        correct_index=0,
        correct_indices=[0],
        explanation="TCP garantiza entrega confiable.",
        position=0,
        source_chunk_position=0,
    )
    chunk = DocumentChunk(
        id=uuid4(),
        document_id=document.id,
        organization_id=org.id,
        position=0,
        content="La capa de transporte garantiza la entrega confiable mediante TCP.",
        embedding=hashed_embedding("tcp"),
        page_start=7,
        page_end=7,
        chapter="Capítulo 3",
        section=None,
    )
    service = EvidenceService(FakeSession())
    service.repo = FakeEvidenceRepo()
    service.chunks = FakeChunkRepo([chunk])

    row = await service.create_from_generation(
        question=question,
        organization_id=org.id,
        document_id=document.id,
        chunk_position=0,
        anchor="entrega confiable mediante TCP",
        explanation=question.explanation or "",
        model="test-model",
    )

    assert row is not None
    assert row.quote
    assert row.verified is True
    assert row.page_start == 7
    assert row.chapter == "Capítulo 3"
    assert row.source is EvidenceSource.GENERATION
    assert len(service.repo.evidence) == 1


@pytest.mark.asyncio
async def test_snapshot_attempt_copies_evidence():
    org = make_org()
    owner = uuid4()
    document = make_document(org.id, owner)
    document.display_title = "Guía de redes"
    exam = make_exam(org.id, owner, document.id, status=ExamStatus.READY)
    question = Question(
        id=uuid4(),
        exam_id=exam.id,
        prompt="Q",
        kind=QuestionKind.SINGLE_CHOICE,
        options=["A", "B", "C", "D"],
        correct_index=0,
        correct_indices=[0],
        position=0,
    )
    exam.questions = [question]
    attempt = ExamAttempt(
        id=uuid4(),
        exam_id=exam.id,
        user_id=owner,
        organization_id=org.id,
        score=100,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        answers={},
    )
    evidence = QuestionEvidence(
        id=uuid4(),
        organization_id=org.id,
        question_id=question.id,
        document_id=document.id,
        quote="Fragmento fuente de la respuesta correcta.",
        page_start=4,
        page_end=4,
        chapter=None,
        section=None,
        confidence=0.9,
        relevance=0.7,
        model="test",
        generated_at=datetime.now(timezone.utc),
        source=EvidenceSource.GENERATION,
        verified=True,
    )
    service = EvidenceService(FakeSession())
    service.repo = FakeEvidenceRepo()
    service.repo.evidence.append(evidence)

    snapshots = await service.snapshot_attempt(attempt=attempt, exam=exam, document=document)
    assert question.id in snapshots
    assert snapshots[question.id].document_title == "Guía de redes"
    assert snapshots[question.id].quote == evidence.quote

    reads = await service.reads_for_attempt(
        organization_id=org.id,
        attempt_id=attempt.id,
        question_ids=[question.id],
        document=document,
    )
    assert reads[question.id].page_start == 4
    assert reads[question.id].document_title == "Guía de redes"

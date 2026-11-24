from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.files import display_name
from app.models.ai_audit import AiFeature
from app.models.document import Document
from app.models.evidence import AnswerReference, EvidenceSource, QuestionEvidence
from app.models.exam import Exam, ExamAttempt, Question
from app.repositories.chunks import ChunkRepository
from app.repositories.evidence import EvidenceRepository
from app.schemas.content import EvidenceRead
from app.services.ai_audit import AiAuditService
from app.services.citations import CitationEngine

settings = get_settings()


class EvidenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = EvidenceRepository(session)
        self.chunks = ChunkRepository(session)
        self.citations = CitationEngine()
        self.ai_audit = AiAuditService(session)

    async def create_from_generation(
        self,
        *,
        question: Question,
        organization_id: UUID,
        document_id: UUID,
        chunk_position: int | None,
        anchor: str = "",
        claim: str = "",
        explanation: str = "",
        model: str | None = None,
    ) -> QuestionEvidence | None:
        if chunk_position is None:
            return None
        chunk = await self.chunks.get_by_position(document_id, organization_id, chunk_position)
        if chunk is None:
            return None
        citation = self.citations.cite(
            chunk_content=chunk.content,
            chunk_id=chunk.id,
            chunk_position=chunk.position,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            chapter=chunk.chapter,
            section=chunk.section,
            anchor=anchor,
            claim=claim,
            explanation=explanation or (question.explanation or ""),
        )
        if citation is None or not citation.quote:
            return None
        row = QuestionEvidence(
            organization_id=organization_id,
            question_id=question.id,
            document_id=document_id,
            chunk_id=citation.chunk_id,
            quote=citation.quote,
            page_start=citation.page_start,
            page_end=citation.page_end,
            chapter=citation.chapter,
            section=citation.section,
            confidence=citation.confidence,
            relevance=citation.relevance,
            model=model or settings.llm_model,
            source=EvidenceSource.GENERATION,
            verified=citation.verified,
        )
        saved = await self.repo.add_evidence(row)
        await self.ai_audit.record(
            organization_id=organization_id,
            feature=AiFeature.EVIDENCE,
            outcome="verified" if citation.verified else "unverified",
            document_id=document_id,
            model=model or settings.llm_model,
            chunk_ids=[citation.chunk_id] if citation.chunk_id else [],
            confidence=citation.confidence,
            relevance=citation.relevance,
            payload={
                "question_id": str(question.id),
                "evidence_id": str(saved.id),
                "page_start": citation.page_start,
                "page_end": citation.page_end,
            },
        )
        return saved

    async def snapshot_attempt(
        self,
        *,
        attempt: ExamAttempt,
        exam: Exam,
        document: Document | None,
    ) -> dict[UUID, AnswerReference]:
        question_ids = [question.id for question in exam.questions]
        evidence_map = await self.repo.list_for_questions(attempt.organization_id, question_ids)
        title = ""
        document_id = exam.document_id
        if document is not None:
            title = display_name(document.display_title, document.filename)
            document_id = document.id
        rows: list[AnswerReference] = []
        for question in exam.questions:
            evidence = evidence_map.get(question.id)
            if evidence is None:
                continue
            rows.append(
                AnswerReference(
                    organization_id=attempt.organization_id,
                    attempt_id=attempt.id,
                    question_id=question.id,
                    evidence_id=evidence.id,
                    document_id=document_id or evidence.document_id,
                    document_title=title,
                    quote=evidence.quote,
                    page_start=evidence.page_start,
                    page_end=evidence.page_end,
                    chapter=evidence.chapter,
                    section=evidence.section,
                    confidence=evidence.confidence,
                    generated_at=evidence.generated_at,
                )
            )
        await self.repo.add_references(rows)
        return {row.question_id: row for row in rows}

    async def reads_for_attempt(
        self,
        *,
        organization_id: UUID,
        attempt_id: UUID,
        question_ids: list[UUID],
        document: Document | None = None,
    ) -> dict[UUID, EvidenceRead]:
        snapshots = await self.repo.list_for_attempt(organization_id, attempt_id)
        if snapshots:
            return {
                question_id: _from_reference(row)
                for question_id, row in snapshots.items()
            }
        evidence_map = await self.repo.list_for_questions(organization_id, question_ids)
        title = display_name(document.display_title, document.filename) if document else ""
        return {
            question_id: _from_evidence(row, document_title=title)
            for question_id, row in evidence_map.items()
        }


def _from_reference(row: AnswerReference) -> EvidenceRead:
    return EvidenceRead(
        quote=row.quote,
        document_id=row.document_id,
        document_title=row.document_title or None,
        page_start=row.page_start,
        page_end=row.page_end,
        chapter=row.chapter,
        section=row.section,
        confidence=row.confidence,
        generated_at=row.generated_at,
        verified=True,
    )


def _from_evidence(row: QuestionEvidence, *, document_title: str = "") -> EvidenceRead:
    return EvidenceRead(
        quote=row.quote,
        document_id=row.document_id,
        document_title=document_title or None,
        page_start=row.page_start,
        page_end=row.page_end,
        chapter=row.chapter,
        section=row.section,
        confidence=row.confidence,
        relevance=row.relevance,
        model=row.model or None,
        generated_at=row.generated_at,
        verified=row.verified,
        source=row.source.value if hasattr(row.source, "value") else str(row.source),
    )

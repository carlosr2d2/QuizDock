from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence import AnswerReference, QuestionEvidence


class EvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_evidence(self, row: QuestionEvidence) -> QuestionEvidence:
        self.session.add(row)
        await self.session.flush()
        return row

    async def add_references(self, rows: list[AnswerReference]) -> None:
        if not rows:
            return
        self.session.add_all(rows)
        await self.session.flush()

    async def list_for_questions(
        self,
        organization_id: UUID,
        question_ids: list[UUID],
    ) -> dict[UUID, QuestionEvidence]:
        if not question_ids:
            return {}
        result = await self.session.execute(
            select(QuestionEvidence)
            .where(
                QuestionEvidence.organization_id == organization_id,
                QuestionEvidence.question_id.in_(question_ids),
            )
            .order_by(QuestionEvidence.created_at.desc())
        )
        mapping: dict[UUID, QuestionEvidence] = {}
        for row in result.scalars().all():
            mapping.setdefault(row.question_id, row)
        return mapping

    async def list_for_attempt(
        self,
        organization_id: UUID,
        attempt_id: UUID,
    ) -> dict[UUID, AnswerReference]:
        result = await self.session.execute(
            select(AnswerReference).where(
                AnswerReference.organization_id == organization_id,
                AnswerReference.attempt_id == attempt_id,
            )
        )
        return {row.question_id: row for row in result.scalars().all()}

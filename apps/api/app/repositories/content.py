from datetime import datetime, timezone
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    CreditTransaction,
    Document,
    Exam,
    ExamAssignment,
    ExamAttempt,
    ExamStatus,
    Flashcard,
    GenerationJob,
    Question,
    User,
)
from app.models.exam import AssignmentStatus


@dataclass
class ExamAttemptStats:
    attempt_count: int = 0
    last_score: float | None = None
    last_attempt_at: datetime | None = None


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_org(self, organization_id: UUID) -> list[Document]:
        result = await self.session.execute(
            select(Document)
            .where(Document.organization_id == organization_id)
            .order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, document_id: UUID, organization_id: UUID) -> Document | None:
        result = await self.session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, document_id: UUID) -> Document | None:
        result = await self.session.execute(select(Document).where(Document.id == document_id))
        return result.scalar_one_or_none()

    async def get_many(self, document_ids: set[UUID], organization_id: UUID) -> dict[UUID, Document]:
        if not document_ids:
            return {}
        result = await self.session.execute(
            select(Document).where(
                Document.id.in_(document_ids),
                Document.organization_id == organization_id,
            )
        )
        return {document.id: document for document in result.scalars().all()}

    async def add(self, document: Document) -> Document:
        self.session.add(document)
        await self.session.flush()
        return document


class ExamRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_org(self, organization_id: UUID) -> list[Exam]:
        result = await self.session.execute(
            select(Exam).where(Exam.organization_id == organization_id).order_by(Exam.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, exam_id: UUID, organization_id: UUID) -> Exam | None:
        result = await self.session.execute(
            select(Exam)
            .options(selectinload(Exam.questions))
            .where(Exam.id == exam_id, Exam.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, exam_id: UUID) -> Exam | None:
        result = await self.session.execute(
            select(Exam).options(selectinload(Exam.questions)).where(Exam.id == exam_id)
        )
        return result.scalar_one_or_none()

    async def add(self, exam: Exam) -> Exam:
        self.session.add(exam)
        await self.session.flush()
        return exam

    async def add_questions(self, questions: list[Question]) -> None:
        self.session.add_all(questions)
        await self.session.flush()

    async def add_attempt(self, attempt: ExamAttempt) -> ExamAttempt:
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def used_chunk_positions(self, document_id: UUID, organization_id: UUID) -> set[int]:
        result = await self.session.execute(
            select(Question.source_chunk_position)
            .join(Exam, Question.exam_id == Exam.id)
            .where(
                Exam.document_id == document_id,
                Exam.organization_id == organization_id,
                Exam.status == ExamStatus.READY,
                Question.source_chunk_position.isnot(None),
            )
        )
        return {position for (position,) in result.all() if position is not None}

    async def list_attempts(
        self,
        exam_id: UUID,
        organization_id: UUID,
        user_id: UUID,
    ) -> list[ExamAttempt]:
        result = await self.session.execute(
            select(ExamAttempt)
            .where(
                ExamAttempt.exam_id == exam_id,
                ExamAttempt.organization_id == organization_id,
                ExamAttempt.user_id == user_id,
                ExamAttempt.completed_at.isnot(None),
            )
            .order_by(ExamAttempt.completed_at.desc())
        )
        return list(result.scalars().all())

    async def get_attempt(
        self,
        attempt_id: UUID,
        exam_id: UUID,
        organization_id: UUID,
        user_id: UUID | None = None,
    ) -> ExamAttempt | None:
        conditions = [
            ExamAttempt.id == attempt_id,
            ExamAttempt.exam_id == exam_id,
            ExamAttempt.organization_id == organization_id,
        ]
        if user_id is not None:
            conditions.append(ExamAttempt.user_id == user_id)
        result = await self.session.execute(select(ExamAttempt).where(*conditions))
        return result.scalar_one_or_none()

    async def stats_for_exams(
        self,
        exam_ids: set[UUID],
        organization_id: UUID,
        user_id: UUID,
    ) -> dict[UUID, ExamAttemptStats]:
        empty = {exam_id: ExamAttemptStats() for exam_id in exam_ids}
        if not exam_ids:
            return empty
        ranked = (
            select(
                ExamAttempt.exam_id,
                ExamAttempt.score,
                ExamAttempt.completed_at,
                func.row_number()
                .over(partition_by=ExamAttempt.exam_id, order_by=ExamAttempt.completed_at.desc())
                .label("rn"),
                func.count().over(partition_by=ExamAttempt.exam_id).label("attempt_count"),
            ).where(
                ExamAttempt.exam_id.in_(exam_ids),
                ExamAttempt.organization_id == organization_id,
                ExamAttempt.user_id == user_id,
                ExamAttempt.completed_at.isnot(None),
            )
        ).subquery()
        result = await self.session.execute(select(ranked).where(ranked.c.rn == 1))
        for row in result.all():
            empty[row.exam_id] = ExamAttemptStats(
                attempt_count=int(row.attempt_count),
                last_score=row.score,
                last_attempt_at=row.completed_at,
            )
        return empty

    async def progress_aggregates(
        self,
        organization_id: UUID,
        user_id: UUID,
    ) -> tuple[int, int, float | None, float | None]:
        result = await self.session.execute(
            select(
                func.count(ExamAttempt.id),
                func.count(func.distinct(ExamAttempt.exam_id)),
                func.avg(ExamAttempt.score),
                func.max(ExamAttempt.score),
            ).where(
                ExamAttempt.organization_id == organization_id,
                ExamAttempt.user_id == user_id,
                ExamAttempt.completed_at.isnot(None),
            )
        )
        count, taken, average, best = result.one()
        return (
            int(count or 0),
            int(taken or 0),
            float(average) if average is not None else None,
            float(best) if best is not None else None,
        )

    async def recent_attempts(
        self,
        organization_id: UUID,
        user_id: UUID,
        limit: int = 8,
    ) -> list[tuple[ExamAttempt, str]]:
        result = await self.session.execute(
            select(ExamAttempt, Exam.title)
            .join(Exam, Exam.id == ExamAttempt.exam_id)
            .where(
                ExamAttempt.organization_id == organization_id,
                ExamAttempt.user_id == user_id,
                ExamAttempt.completed_at.isnot(None),
            )
            .order_by(ExamAttempt.completed_at.desc())
            .limit(limit)
        )
        return [(attempt, title) for attempt, title in result.all()]

    async def retitle_from_filename(
        self,
        document_id: UUID,
        filename: str,
        title: str,
        previous_title: str | None = None,
    ) -> None:
        result = await self.session.execute(select(Exam).where(Exam.document_id == document_id))
        for exam in result.scalars():
            current = exam.title or ""
            if (
                filename in current
                or current.startswith("Cuestionario")
                or (previous_title and current == previous_title)
                or (" " not in current.strip() and len(current.strip()) < 16)
            ):
                exam.title = title

    async def add_assignment(self, assignment: ExamAssignment) -> ExamAssignment:
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def get_assignment(
        self,
        exam_id: UUID,
        user_id: UUID,
        organization_id: UUID,
    ) -> ExamAssignment | None:
        result = await self.session.execute(
            select(ExamAssignment).where(
                ExamAssignment.exam_id == exam_id,
                ExamAssignment.user_id == user_id,
                ExamAssignment.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_assignments(self, exam_id: UUID, organization_id: UUID) -> list[ExamAssignment]:
        result = await self.session.execute(
            select(ExamAssignment)
            .where(
                ExamAssignment.exam_id == exam_id,
                ExamAssignment.organization_id == organization_id,
            )
            .order_by(ExamAssignment.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_assignments_for_user(
        self,
        organization_id: UUID,
        user_id: UUID,
    ) -> list[ExamAssignment]:
        result = await self.session.execute(
            select(ExamAssignment).where(
                ExamAssignment.organization_id == organization_id,
                ExamAssignment.user_id == user_id,
            )
        )
        return list(result.scalars().all())

    async def list_assignments_for_user_with_titles(
        self,
        organization_id: UUID,
        user_id: UUID,
    ) -> list[tuple[ExamAssignment, str]]:
        result = await self.session.execute(
            select(ExamAssignment, Exam.title)
            .join(Exam, Exam.id == ExamAssignment.exam_id)
            .where(
                ExamAssignment.organization_id == organization_id,
                ExamAssignment.user_id == user_id,
            )
            .order_by(ExamAssignment.created_at.desc())
        )
        return [(assignment, title) for assignment, title in result.all()]

    async def assignment_counts(
        self,
        exam_ids: set[UUID],
        organization_id: UUID,
    ) -> dict[UUID, tuple[int, int]]:
        empty = {exam_id: (0, 0) for exam_id in exam_ids}
        if not exam_ids:
            return empty
        result = await self.session.execute(
            select(
                ExamAssignment.exam_id,
                func.count(ExamAssignment.id),
                func.sum(case((ExamAssignment.status == AssignmentStatus.COMPLETED, 1), else_=0)),
            )
            .where(
                ExamAssignment.exam_id.in_(exam_ids),
                ExamAssignment.organization_id == organization_id,
            )
            .group_by(ExamAssignment.exam_id)
        )
        for exam_id, total, completed in result.all():
            empty[exam_id] = (int(total or 0), int(completed or 0))
        return empty

    async def latest_attempts(
        self,
        exam_id: UUID,
        organization_id: UUID,
        user_ids: set[UUID],
    ) -> dict[UUID, tuple[float | None, UUID | None]]:
        empty: dict[UUID, tuple[float | None, UUID | None]] = {user_id: (None, None) for user_id in user_ids}
        if not user_ids:
            return empty
        ranked = (
            select(
                ExamAttempt.user_id,
                ExamAttempt.score,
                ExamAttempt.id,
                func.row_number()
                .over(partition_by=ExamAttempt.user_id, order_by=ExamAttempt.completed_at.desc())
                .label("rn"),
            ).where(
                ExamAttempt.exam_id == exam_id,
                ExamAttempt.organization_id == organization_id,
                ExamAttempt.user_id.in_(user_ids),
                ExamAttempt.completed_at.isnot(None),
            )
        ).subquery()
        result = await self.session.execute(select(ranked).where(ranked.c.rn == 1))
        for row in result.all():
            empty[row.user_id] = (row.score, row.id)
        return empty

    async def delete_assignment(self, assignment: ExamAssignment) -> None:
        await self.session.delete(assignment)
        await self.session.flush()

    async def users_by_ids(self, user_ids: set[UUID]) -> dict[UUID, User]:
        if not user_ids:
            return {}
        result = await self.session.execute(select(User).where(User.id.in_(user_ids)))
        return {user.id: user for user in result.scalars().all()}


class FlashcardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_org(
        self,
        organization_id: UUID,
        owner_user_id: UUID | None = None,
        due_only: bool = False,
        document_id: UUID | None = None,
    ) -> list[Flashcard]:
        stmt = select(Flashcard).where(Flashcard.organization_id == organization_id)
        if owner_user_id is not None:
            stmt = stmt.where(Flashcard.owner_user_id == owner_user_id)
        if document_id is not None:
            stmt = stmt.where(Flashcard.document_id == document_id)
        if due_only:
            now = datetime.now(timezone.utc)
            stmt = stmt.where(
                (Flashcard.next_review_at.is_(None)) | (Flashcard.next_review_at <= now)
            )
            stmt = stmt.order_by(Flashcard.next_review_at.asc().nulls_first())
        else:
            stmt = stmt.order_by(Flashcard.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def deck_stats(
        self,
        organization_id: UUID,
        owner_user_id: UUID,
    ) -> list[tuple[UUID | None, int, int, datetime | None]]:
        now = datetime.now(timezone.utc)
        due = or_(Flashcard.next_review_at.is_(None), Flashcard.next_review_at <= now)
        result = await self.session.execute(
            select(
                Flashcard.document_id,
                func.count(Flashcard.id),
                func.coalesce(func.sum(case((due, 1), else_=0)), 0),
                func.max(Flashcard.last_reviewed_at),
            )
            .where(
                Flashcard.organization_id == organization_id,
                Flashcard.owner_user_id == owner_user_id,
            )
            .group_by(Flashcard.document_id)
            .order_by(func.coalesce(func.sum(case((due, 1), else_=0)), 0).desc())
        )
        return [
            (row[0], int(row[1] or 0), int(row[2] or 0), row[3])
            for row in result.all()
        ]

    async def progress_aggregates(
        self,
        organization_id: UUID,
        owner_user_id: UUID,
    ) -> tuple[int, int, int, datetime | None]:
        now = datetime.now(timezone.utc)
        due = or_(Flashcard.next_review_at.is_(None), Flashcard.next_review_at <= now)
        result = await self.session.execute(
            select(
                func.count(Flashcard.id),
                func.coalesce(func.sum(case((due, 1), else_=0)), 0),
                func.coalesce(func.sum(case((Flashcard.repetitions > 0, 1), else_=0)), 0),
                func.max(Flashcard.last_reviewed_at),
            ).where(
                Flashcard.organization_id == organization_id,
                Flashcard.owner_user_id == owner_user_id,
            )
        )
        total, due_count, reviewed, last_at = result.one()
        return int(total or 0), int(due_count or 0), int(reviewed or 0), last_at

    async def get(self, card_id: UUID, organization_id: UUID, owner_user_id: UUID) -> Flashcard | None:
        result = await self.session.execute(
            select(Flashcard).where(
                Flashcard.id == card_id,
                Flashcard.organization_id == organization_id,
                Flashcard.owner_user_id == owner_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def add(self, flashcard: Flashcard) -> Flashcard:
        self.session.add(flashcard)
        await self.session.flush()
        return flashcard

    async def add_many(self, cards: list[Flashcard]) -> None:
        self.session.add_all(cards)
        await self.session.flush()


class BillingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_transaction(self, tx: CreditTransaction) -> CreditTransaction:
        self.session.add(tx)
        await self.session.flush()
        return tx


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, job_id: UUID, organization_id: UUID) -> GenerationJob | None:
        result = await self.session.execute(
            select(GenerationJob).where(
                GenerationJob.id == job_id,
                GenerationJob.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, job_id: UUID) -> GenerationJob | None:
        result = await self.session.execute(select(GenerationJob).where(GenerationJob.id == job_id))
        return result.scalar_one_or_none()

    async def add(self, job: GenerationJob) -> GenerationJob:
        self.session.add(job)
        await self.session.flush()
        return job

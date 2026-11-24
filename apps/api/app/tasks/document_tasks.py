from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.worker import run_worker_job
from app.services.content import DocumentService
from app.services.generation import ExamService, FlashcardGenerationService


@celery_app.task(name="documents.process")
def process_document(document_id: str) -> str:
    async def _job(session: AsyncSession) -> None:
        await DocumentService(session).process(UUID(document_id))

    run_worker_job(_job)
    return document_id


@celery_app.task(name="assessments.generate_exam")
def generate_exam(exam_id: str) -> str:
    async def _job(session: AsyncSession) -> None:
        await ExamService(session).fulfill(UUID(exam_id))

    run_worker_job(_job)
    return exam_id


@celery_app.task(name="assessments.generate_flashcards")
def generate_flashcards(job_id: str) -> str:
    async def _job(session: AsyncSession) -> None:
        await FlashcardGenerationService(session).fulfill(UUID(job_id))

    run_worker_job(_job)
    return job_id


@celery_app.task(name="appeals.ai_review")
def appeal_ai_review(recommendation_id: str) -> str:
    from app.services.appeal_ai import AppealAiService

    async def _job(session: AsyncSession) -> None:
        await AppealAiService(session).fulfill(UUID(recommendation_id))

    run_worker_job(_job)
    return recommendation_id

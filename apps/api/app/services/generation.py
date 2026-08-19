from datetime import datetime, timezone
import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.files import display_name
from app.core.jobs import enqueue
from app.models import (
    DocumentStatus,
    Exam,
    ExamAssignment,
    ExamAttempt,
    ExamKind,
    ExamStatus,
    Flashcard,
    GenerationJob,
    MembershipRole,
    Question,
    QuestionKind,
)
from app.models.exam import AssignmentStatus
from app.repositories.content import DocumentRepository, ExamRepository, FlashcardRepository, JobRepository
from app.repositories.identity import MembershipRepository, OrganizationRepository
from app.schemas.content import (
    AssignmentRead,
    AttemptRead,
    AttemptSubmit,
    AttemptSummary,
    ExamAssignRequest,
    ExamDetail,
    ExamGenerateRequest,
    ExamRead,
    FlashcardGenerateRequest,
    ProgressAttempt,
    MemberAssignmentProgress,
    MemberProgressRead,
    ProgressRead,
    QuestionPublic,
    QuestionResult,
    exam_read,
)
from app.services.billing import BillingService
from app.services.errors import ConflictError, DomainError, ForbiddenError, NotFoundError
from app.services.llm import generate_exam_from_contexts, generate_flashcards_from_contexts
from app.services.permissions import require_author
from app.services.rag import RagService

settings = get_settings()

MANAGE_ROLES = {MembershipRole.OWNER, MembershipRole.ADMIN}
CATALOG_ROLES = {MembershipRole.OWNER, MembershipRole.ADMIN, MembershipRole.AUDITOR}


def answer_indices(value: object) -> list[int]:
    if value is None:
        return []
    if isinstance(value, bool):
        return []
    if isinstance(value, list):
        return sorted({int(item) for item in value if isinstance(item, (int, float)) and int(item) >= 0})
    if isinstance(value, int) and value >= 0:
        return [value]
    if isinstance(value, str) and value.isdigit():
        return [int(value)]
    return []


def question_correct_indices(question: Question) -> list[int]:
    stored = question.correct_indices or []
    if stored:
        return sorted({int(index) for index in stored})
    return [question.correct_index]


def question_kind(question: Question) -> QuestionKind:
    return QuestionKind.parse(question.kind)


class ExamService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ExamRepository(session)
        self.documents = DocumentRepository(session)
        self.memberships = MembershipRepository(session)
        self.orgs = OrganizationRepository(session)
        self.billing = BillingService(session)

    async def list_reads(
        self,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
    ) -> list[ExamRead]:
        org = await self._org(organization_id)
        exams = await self.repo.list_for_org(organization_id)
        mine = {
            item.exam_id: item
            for item in await self.repo.list_assignments_for_user(organization_id, user_id)
        }
        if not self._sees_catalog(org, role):
            exams = [exam for exam in exams if exam.id in mine]
        documents = await self.documents.get_many(
            {exam.document_id for exam in exams if exam.document_id},
            organization_id,
        )
        stats_map = await self.repo.stats_for_exams({exam.id for exam in exams}, organization_id, user_id)
        counts = await self.repo.assignment_counts({exam.id for exam in exams}, organization_id)
        can_assign = self._can_assign(org, role)
        items: list[ExamRead] = []
        for exam in exams:
            stats = stats_map[exam.id]
            assignment = mine.get(exam.id)
            total, completed = counts[exam.id]
            items.append(
                exam_read(
                    exam,
                    documents.get(exam.document_id) if exam.document_id else None,
                    attempt_count=stats.attempt_count,
                    last_score=stats.last_score,
                    last_attempt_at=stats.last_attempt_at,
                    assigned_to_me=assignment is not None,
                    assignment_status=str(assignment.status) if assignment else None,
                    assignment_count=total,
                    assignment_completed_count=completed,
                    can_assign=can_assign,
                )
            )
        return items

    async def get(self, exam_id: UUID, organization_id: UUID) -> Exam:
        exam = await self.repo.get(exam_id, organization_id)
        if exam is None:
            raise NotFoundError("Exam not found")
        return exam

    async def get_detail(
        self,
        exam_id: UUID,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
    ) -> ExamDetail:
        org = await self._org(organization_id)
        exam = await self.get(exam_id, organization_id)
        assignment = await self.repo.get_assignment(exam.id, user_id, organization_id)
        if not self._sees_catalog(org, role) and assignment is None:
            raise ForbiddenError("Este examen no te fue asignado.")
        document = None
        if exam.document_id:
            document = await self.documents.get(exam.document_id, organization_id)
        stats = (await self.repo.stats_for_exams({exam.id}, organization_id, user_id))[exam.id]
        questions = []
        if exam.status != ExamStatus.GENERATING:
            questions = [
                QuestionPublic.model_validate(question)
                for question in sorted(exam.questions, key=lambda item: item.position)
            ]
        attempts = [
            AttemptSummary(
                id=item.id,
                exam_id=item.exam_id,
                score=item.score or 0,
                completed_at=item.completed_at,
            )
            for item in await self.repo.list_attempts(exam.id, organization_id, user_id)
            if item.completed_at is not None
        ]
        total, completed = (await self.repo.assignment_counts({exam.id}, organization_id))[exam.id]
        roster = []
        if self._sees_catalog(org, role) and not org.is_personal:
            roster = await self.list_assignment_reads(exam.id, organization_id)
        return ExamDetail(
            **exam_read(
                exam,
                document,
                attempt_count=stats.attempt_count,
                last_score=stats.last_score,
                last_attempt_at=stats.last_attempt_at,
                assigned_to_me=assignment is not None,
                assignment_status=str(assignment.status) if assignment else None,
                assignment_count=total,
                assignment_completed_count=completed,
                can_assign=self._can_assign(org, role),
            ).model_dump(),
            questions=questions,
            attempts=attempts,
            assignments=roster,
        )

    async def progress(
        self, organization_id: UUID, user_id: UUID, *, limit: int = 8
    ) -> ProgressRead:
        attempt_count, exams_taken, average, best = await self.repo.progress_aggregates(
            organization_id, user_id
        )
        recent_rows = await self.repo.recent_attempts(organization_id, user_id, limit=limit)
        recent = [
            ProgressAttempt(
                id=attempt.id,
                exam_id=attempt.exam_id,
                exam_title=title,
                score=attempt.score or 0,
                completed_at=attempt.completed_at or attempt.created_at,
            )
            for attempt, title in recent_rows
        ]
        return ProgressRead(
            attempt_count=attempt_count,
            exams_taken=exams_taken,
            average_score=round(average, 1) if average is not None else None,
            best_score=round(best, 1) if best is not None else None,
            last_score=recent[0].score if recent else None,
            recent=recent,
        )

    async def member_progress(
        self,
        organization_id: UUID,
        actor_id: UUID,
        actor_role: MembershipRole,
        target_user_id: UUID,
    ) -> MemberProgressRead:
        org = await self._org(organization_id)
        membership = await self.memberships.get_with_user(target_user_id, organization_id)
        if membership is None or membership.user is None:
            raise NotFoundError("Miembro no encontrado")
        if target_user_id != actor_id and not self._can_review_attempts(org, actor_role):
            raise ForbiddenError("No puedes ver el progreso de otro miembro.")

        snapshot = await self.progress(organization_id, target_user_id, limit=20)
        rows = await self.repo.list_assignments_for_user_with_titles(organization_id, target_user_id)
        exam_ids = {item.exam_id for item, _title in rows}
        latest: dict[UUID, tuple[float | None, UUID | None]] = {}
        for exam_id in exam_ids:
            scores = await self.repo.latest_attempts(exam_id, organization_id, {target_user_id})
            latest[exam_id] = scores.get(target_user_id, (None, None))

        assignments: list[MemberAssignmentProgress] = []
        pending = 0
        for item, title in rows:
            status = item.status.value if hasattr(item.status, "value") else str(item.status)
            status = status.rsplit(".", 1)[-1].lower()
            if status != "completed":
                pending += 1
            score, attempt_id = latest.get(item.exam_id, (None, None))
            assignments.append(
                MemberAssignmentProgress(
                    exam_id=item.exam_id,
                    exam_title=title,
                    status=status,
                    last_score=score,
                    last_attempt_id=attempt_id,
                    completed_at=item.completed_at,
                )
            )

        return MemberProgressRead(
            user_id=target_user_id,
            full_name=membership.user.full_name,
            email=membership.user.email,
            role=str(membership.role.value if hasattr(membership.role, "value") else membership.role),
            attempt_count=snapshot.attempt_count,
            exams_taken=snapshot.exams_taken,
            average_score=snapshot.average_score,
            best_score=snapshot.best_score,
            last_score=snapshot.last_score,
            assigned_count=len(assignments),
            assigned_pending_count=pending,
            recent=snapshot.recent,
            assignments=assignments,
        )

    async def request_generation(
        self,
        organization_id: UUID,
        owner_user_id: UUID,
        role: MembershipRole,
        payload: ExamGenerateRequest,
    ) -> ExamRead:
        require_author(role)
        document = await self.documents.get(payload.document_id, organization_id)
        if document is None:
            raise NotFoundError("Document not found")
        if document.status != DocumentStatus.READY or not document.extracted_text:
            raise ConflictError("El documento aún no está listo para generar evaluaciones")

        cost = payload.question_count * settings.credit_cost_per_question
        await self.billing.debit(organization_id, owner_user_id, cost, "exam_generate")

        title = payload.title or display_name(document.display_title, document.filename)
        exam = Exam(
            organization_id=organization_id,
            owner_user_id=owner_user_id,
            document_id=document.id,
            title=title,
            kind=payload.kind or ExamKind.QUIZ,
            status=ExamStatus.GENERATING,
            question_count=payload.question_count,
            generated_count=0,
            credit_cost=cost,
        )
        await self.repo.add(exam)
        await self.session.commit()
        await self.session.refresh(exam)

        if not enqueue("assessments.generate_exam", str(exam.id)):
            exam.status = ExamStatus.DRAFT
            exam.error_message = "No se pudo encolar el trabajo de generación"
            await self.billing.credit(organization_id, owner_user_id, cost, "exam_generate_refund")
            await self.session.commit()
            raise ConflictError("El worker no está disponible. Inténtalo de nuevo.")
        return exam_read(exam, document)

    async def fulfill(self, exam_id: UUID) -> None:
        try:
            exam = await self.repo.get_by_id(exam_id)
        except Exception:
            return
        if exam is None:
            return
        if exam.status == ExamStatus.READY:
            return
        if exam.status != ExamStatus.GENERATING:
            return

        existing = list(exam.questions)
        target = exam.question_count or 8
        if len(existing) >= target:
            exam.generated_count = len(existing)
            exam.question_count = len(existing)
            exam.status = ExamStatus.READY
            await self.session.commit()
            return

        try:
            document = await self.documents.get_by_id(exam.document_id) if exam.document_id else None
            if document is None or not document.extracted_text:
                await self._fail_exam(exam, "Documento sin texto extraído")
                return
            needed = target - len(existing)
            exam.generated_count = len(existing)
            await self.session.commit()
            used = await self.repo.used_chunk_positions(document.id, exam.organization_id)
            lock = asyncio.Lock()
            saved = len(existing)

            async def persist(item) -> None:
                nonlocal saved
                async with lock:
                    await self.repo.add_questions(
                        [
                            Question(
                                exam_id=exam.id,
                                prompt=item.prompt,
                                kind=QuestionKind.parse(item.kind),
                                options=item.options,
                                correct_index=(
                                    item.correct_index
                                    if item.correct_index is not None
                                    else item.correct_indices[0]
                                ),
                                correct_indices=item.correct_indices,
                                explanation=item.explanation,
                                difficulty=item.difficulty,
                                position=saved,
                                source_chunk_position=item.source_chunk_position,
                            )
                        ]
                    )
                    saved += 1
                    exam.generated_count = saved
                    await self.session.commit()

            generated = await generate_exam_from_contexts(
                await RagService(self.session).contexts_for(
                    document,
                    needed,
                    seed=exam.id,
                    exclude_positions=used,
                ),
                needed,
                document.language or "es",
                exam.title,
                on_question=persist,
            )
            exam.title = generated.title or exam.title
            exam.question_count = saved
            exam.generated_count = saved
            exam.status = ExamStatus.READY
            exam.error_message = None
            await self.session.commit()
        except Exception as exc:
            await self._fail_exam(exam, str(exc))

    async def submit_attempt(
        self,
        exam_id: UUID,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
        payload: AttemptSubmit,
    ) -> AttemptRead:
        org = await self._org(organization_id)
        exam = await self.get(exam_id, organization_id)
        assignment = await self.repo.get_assignment(exam.id, user_id, organization_id)
        if not self._can_take(org, role, assignment):
            raise ForbiddenError("Este examen no te fue asignado.")
        if exam.status != ExamStatus.READY or not exam.questions:
            raise ConflictError("El examen no está listo")

        results: list[QuestionResult] = []
        correct = 0
        serialized_answers: dict[str, list[int]] = {}
        for question in exam.questions:
            selected = answer_indices(payload.answers.get(str(question.id)))
            expected = question_correct_indices(question)
            if selected:
                serialized_answers[str(question.id)] = selected
            is_correct = selected == expected
            if is_correct:
                correct += 1
            results.append(
                QuestionResult(
                    question_id=question.id,
                    prompt=question.prompt,
                    kind=question_kind(question),
                    options=question.options,
                    selected_index=selected[0] if selected else None,
                    selected_indices=selected,
                    correct_index=expected[0],
                    correct_indices=expected,
                    explanation=question.explanation,
                    is_correct=is_correct,
                )
            )
        score = round(100.0 * correct / len(exam.questions), 2)
        now = datetime.now(timezone.utc)
        attempt = ExamAttempt(
            exam_id=exam.id,
            user_id=user_id,
            organization_id=organization_id,
            score=score,
            started_at=now,
            completed_at=now,
            answers=serialized_answers,
        )
        await self.repo.add_attempt(attempt)
        if assignment is not None and assignment.status != AssignmentStatus.COMPLETED:
            assignment.status = AssignmentStatus.COMPLETED
            assignment.completed_at = now
        await self.session.commit()
        await self.session.refresh(attempt)
        actor = await self.repo.users_by_ids({user_id})
        person = actor.get(user_id)
        return AttemptRead(
            id=attempt.id,
            exam_id=exam.id,
            user_id=user_id,
            full_name=person.full_name if person else "",
            email=person.email if person else "",
            is_own=True,
            score=score,
            completed_at=now,
            results=results,
        )

    async def get_attempt(
        self,
        exam_id: UUID,
        attempt_id: UUID,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
    ) -> AttemptRead:
        org = await self._org(organization_id)
        exam = await self.get(exam_id, organization_id)
        attempt = await self.repo.get_attempt(attempt_id, exam_id, organization_id)
        if attempt is None or attempt.completed_at is None:
            raise NotFoundError("Attempt not found")
        is_own = attempt.user_id == user_id
        if not is_own and not self._can_review_attempts(org, role):
            raise ForbiddenError("No puedes ver las respuestas de otro miembro.")
        answers = attempt.answers or {}
        results: list[QuestionResult] = []
        for question in sorted(exam.questions, key=lambda item: item.position):
            raw = answers.get(str(question.id))
            if raw is None:
                raw = answers.get(question.id)
            selected = answer_indices(raw)
            expected = question_correct_indices(question)
            results.append(
                QuestionResult(
                    question_id=question.id,
                    prompt=question.prompt,
                    kind=question_kind(question),
                    options=question.options,
                    selected_index=selected[0] if selected else None,
                    selected_indices=selected,
                    correct_index=expected[0],
                    correct_indices=expected,
                    explanation=question.explanation,
                    is_correct=selected == expected,
                )
            )
        people = await self.repo.users_by_ids({attempt.user_id})
        person = people.get(attempt.user_id)
        return AttemptRead(
            id=attempt.id,
            exam_id=exam.id,
            user_id=attempt.user_id,
            full_name=person.full_name if person else "",
            email=person.email if person else "",
            is_own=is_own,
            score=attempt.score or 0,
            completed_at=attempt.completed_at,
            results=results,
        )

    async def assign(
        self,
        exam_id: UUID,
        organization_id: UUID,
        actor_id: UUID,
        role: MembershipRole,
        payload: ExamAssignRequest,
    ) -> list[AssignmentRead]:
        org = await self._org(organization_id)
        if not self._can_assign(org, role):
            raise ForbiddenError("Solo el propietario o un admin puede asignar exámenes.")
        exam = await self.get(exam_id, organization_id)
        if exam.status != ExamStatus.READY:
            raise ConflictError("Solo se asignan exámenes listos.")
        members = await self.memberships.list_with_users(organization_id)
        member_ids = {item.user_id for item in members}
        targets = member_ids if payload.all_members else set(payload.user_ids)
        unknown = targets - member_ids
        if unknown:
            raise DomainError("Hay usuarios que no pertenecen a este workspace.")
        if not targets:
            raise DomainError("Selecciona al menos un miembro.")
        for user_id in targets:
            existing = await self.repo.get_assignment(exam.id, user_id, organization_id)
            if existing is not None:
                continue
            await self.repo.add_assignment(
                ExamAssignment(
                    organization_id=organization_id,
                    exam_id=exam.id,
                    user_id=user_id,
                    assigned_by_user_id=actor_id,
                    status=AssignmentStatus.PENDING,
                )
            )
        await self.session.commit()
        return await self.list_assignment_reads(exam.id, organization_id)

    async def unassign(
        self,
        exam_id: UUID,
        organization_id: UUID,
        role: MembershipRole,
        user_id: UUID,
    ) -> None:
        org = await self._org(organization_id)
        if not self._can_assign(org, role):
            raise ForbiddenError("Solo el propietario o un admin puede quitar asignaciones.")
        assignment = await self.repo.get_assignment(exam_id, user_id, organization_id)
        if assignment is None:
            raise NotFoundError("Asignación no encontrada")
        if assignment.status == AssignmentStatus.COMPLETED:
            raise DomainError("No se puede quitar una asignación ya completada.")
        await self.repo.delete_assignment(assignment)
        await self.session.commit()

    async def list_assignment_reads(self, exam_id: UUID, organization_id: UUID) -> list[AssignmentRead]:
        items = await self.repo.list_assignments(exam_id, organization_id)
        users = await self.repo.users_by_ids({item.user_id for item in items})
        latest = await self.repo.latest_attempts(exam_id, organization_id, {item.user_id for item in items})
        reads: list[AssignmentRead] = []
        for item in items:
            score, attempt_id = latest.get(item.user_id, (None, None))
            person = users.get(item.user_id)
            reads.append(
                AssignmentRead(
                    id=item.id,
                    user_id=item.user_id,
                    email=person.email if person else "",
                    full_name=person.full_name if person else "",
                    status=str(item.status),
                    completed_at=item.completed_at,
                    last_score=score,
                    last_attempt_id=attempt_id,
                )
            )
        return reads

    async def _org(self, organization_id: UUID):
        org = await self.orgs.get(organization_id)
        if org is None:
            raise NotFoundError("Organization not found")
        return org

    def _sees_catalog(self, org, role: MembershipRole) -> bool:
        return org.is_personal or role in CATALOG_ROLES

    def _can_assign(self, org, role: MembershipRole) -> bool:
        return (not org.is_personal) and role in MANAGE_ROLES

    def _can_review_attempts(self, org, role: MembershipRole) -> bool:
        return org.is_personal or role in CATALOG_ROLES

    def _can_take(self, org, role: MembershipRole, assignment: ExamAssignment | None) -> bool:
        if org.is_personal or role in MANAGE_ROLES:
            return True
        return assignment is not None

    async def _fail_exam(self, exam: Exam, message: str) -> None:
        exam.status = ExamStatus.FAILED
        exam.error_message = message
        if exam.credit_cost:
            await self.billing.credit(
                exam.organization_id,
                exam.owner_user_id,
                exam.credit_cost,
                "exam_generate_refund",
            )
        await self.session.commit()


class FlashcardGenerationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.jobs = JobRepository(session)
        self.documents = DocumentRepository(session)
        self.cards = FlashcardRepository(session)
        self.billing = BillingService(session)

    async def get_job(self, job_id: UUID, organization_id: UUID) -> GenerationJob:
        job = await self.jobs.get(job_id, organization_id)
        if job is None:
            raise NotFoundError("Job not found")
        return job

    async def request(
        self,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
        payload: FlashcardGenerateRequest,
    ) -> GenerationJob:
        require_author(role)
        document = await self.documents.get(payload.document_id, organization_id)
        if document is None:
            raise NotFoundError("Document not found")
        if document.status != DocumentStatus.READY or not document.extracted_text:
            raise ConflictError("El documento aún no está listo para generar flashcards")

        cost = payload.card_count * settings.credit_cost_per_flashcard
        await self.billing.debit(organization_id, user_id, cost, "flashcard_generate")
        job = GenerationJob(
            organization_id=organization_id,
            user_id=user_id,
            document_id=document.id,
            kind="flashcards",
            status="queued",
            credit_cost=cost,
            item_count=payload.card_count,
        )
        await self.jobs.add(job)
        await self.session.commit()
        await self.session.refresh(job)

        if not enqueue("assessments.generate_flashcards", str(job.id)):
            job.status = "failed"
            job.error_message = "No se pudo encolar el trabajo de generación"
            job.refunded = True
            await self.billing.credit(organization_id, user_id, cost, "flashcard_generate_refund")
            await self.session.commit()
            raise ConflictError("El worker no está disponible. Inténtalo de nuevo.")
        return job

    async def fulfill(self, job_id: UUID) -> None:
        job = await self.jobs.get_by_id(job_id)
        if job is None:
            return
        if job.status in {"succeeded", "failed"}:
            return

        job.status = "running"
        await self.session.commit()

        document = await self.documents.get_by_id(job.document_id)
        if document is None or not document.extracted_text:
            await self._fail_job(job, "Documento sin texto extraído")
            return

        try:
            deck = await generate_flashcards_from_contexts(
                await RagService(self.session).contexts_for(
                    document,
                    job.item_count or 12,
                    seed=job.id,
                ),
                job.item_count or 12,
                document.language or "es",
            )
            cards = [
                Flashcard(
                    organization_id=job.organization_id,
                    owner_user_id=job.user_id,
                    document_id=job.document_id,
                    front=item.front,
                    back=item.back,
                )
                for item in deck.cards
            ]
            await self.cards.add_many(cards)
            job.status = "succeeded"
            job.item_count = len(cards)
            job.error_message = None
            await self.session.commit()
        except Exception as exc:
            await self._fail_job(job, str(exc))

    async def _fail_job(self, job: GenerationJob, message: str) -> None:
        job.status = "failed"
        job.error_message = message
        if not job.refunded and job.credit_cost:
            await self.billing.credit(
                job.organization_id,
                job.user_id,
                job.credit_cost,
                "flashcard_generate_refund",
            )
            job.refunded = True
        await self.session.commit()

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequestContext, get_context, get_db, require_roles
from app.models import MembershipRole
from app.schemas.content import (
    AssignmentRead,
    AttemptRead,
    AttemptSubmit,
    ExamAssignRequest,
    ExamDetail,
    ExamGenerateRequest,
    ExamRead,
    FlashcardCreate,
    FlashcardDeckRead,
    FlashcardGenerateRequest,
    FlashcardRead,
    FlashcardReviewRequest,
    GenerationJobRead,
    ProgressRead,
)
from app.services.content import FlashcardService
from app.services.generation import ExamService, FlashcardGenerationService
from app.services.progress import merge_personal_progress
from app.services.permissions import AUTHOR_DENIED, AUTHOR_ROLES

WRITE_ROLES = (MembershipRole.OWNER, MembershipRole.ADMIN, MembershipRole.MEMBER)
ASSIGN_ROLES = (MembershipRole.OWNER, MembershipRole.ADMIN)
CATALOG_ROLES = (MembershipRole.OWNER, MembershipRole.ADMIN, MembershipRole.AUDITOR)

exams_router = APIRouter(prefix="/exams", tags=["exams"])
flashcards_router = APIRouter(prefix="/flashcards", tags=["flashcards"])
jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])
progress_router = APIRouter(prefix="/progress", tags=["progress"])


@exams_router.get("", response_model=list[ExamRead])
async def list_exams(
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> list[ExamRead]:
    return await ExamService(db).list_reads(ctx.organization_id, ctx.user.id, ctx.role)


@exams_router.post("", response_model=ExamRead, status_code=202)
async def generate_exam(
    payload: ExamGenerateRequest,
    ctx: RequestContext = Depends(require_roles(*AUTHOR_ROLES, detail=AUTHOR_DENIED)),
    db: AsyncSession = Depends(get_db),
) -> ExamRead:
    return await ExamService(db).request_generation(
        ctx.organization_id, ctx.user.id, ctx.role, payload
    )


@exams_router.get("/{exam_id}", response_model=ExamDetail)
async def get_exam(
    exam_id: UUID,
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> ExamDetail:
    return await ExamService(db).get_detail(exam_id, ctx.organization_id, ctx.user.id, ctx.role)


@exams_router.get("/{exam_id}/attempts/{attempt_id}", response_model=AttemptRead)
async def get_attempt(
    exam_id: UUID,
    attempt_id: UUID,
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> AttemptRead:
    return await ExamService(db).get_attempt(
        exam_id, attempt_id, ctx.organization_id, ctx.user.id, ctx.role
    )


@exams_router.post("/{exam_id}/attempts", response_model=AttemptRead)
async def submit_attempt(
    exam_id: UUID,
    payload: AttemptSubmit,
    ctx: RequestContext = Depends(require_roles(*WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> AttemptRead:
    return await ExamService(db).submit_attempt(
        exam_id, ctx.organization_id, ctx.user.id, ctx.role, payload
    )


@exams_router.get("/{exam_id}/assignments", response_model=list[AssignmentRead])
async def list_assignments(
    exam_id: UUID,
    ctx: RequestContext = Depends(require_roles(*CATALOG_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> list[AssignmentRead]:
    exam = await ExamService(db).get(exam_id, ctx.organization_id)
    return await ExamService(db).list_assignment_reads(exam.id, ctx.organization_id)


@exams_router.post("/{exam_id}/assignments", response_model=list[AssignmentRead])
async def assign_exam(
    exam_id: UUID,
    payload: ExamAssignRequest,
    ctx: RequestContext = Depends(require_roles(*ASSIGN_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> list[AssignmentRead]:
    return await ExamService(db).assign(
        exam_id, ctx.organization_id, ctx.user.id, ctx.role, payload
    )


@exams_router.delete(
    "/{exam_id}/assignments/{user_id}",
    status_code=204,
    response_class=Response,
)
async def unassign_exam(
    exam_id: UUID,
    user_id: UUID,
    ctx: RequestContext = Depends(require_roles(*ASSIGN_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await ExamService(db).unassign(
        exam_id, ctx.organization_id, ctx.role, user_id, actor_id=ctx.user.id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@flashcards_router.get("", response_model=list[FlashcardRead])
async def list_flashcards(
    due: bool = Query(default=False),
    document_id: UUID | None = Query(default=None),
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> list[FlashcardRead]:
    return await FlashcardService(db).list(
        ctx.organization_id,
        ctx.user.id,
        due_only=due,
        document_id=document_id,
    )


@flashcards_router.get("/decks", response_model=list[FlashcardDeckRead])
async def list_flashcard_decks(
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> list[FlashcardDeckRead]:
    return await FlashcardService(db).list_decks(ctx.organization_id, ctx.user.id)


@flashcards_router.post("", response_model=FlashcardRead, status_code=201)
async def create_flashcard(
    payload: FlashcardCreate,
    ctx: RequestContext = Depends(require_roles(*AUTHOR_ROLES, detail=AUTHOR_DENIED)),
    db: AsyncSession = Depends(get_db),
) -> FlashcardRead:
    card = await FlashcardService(db).create(ctx.organization_id, ctx.user.id, ctx.role, payload)
    return FlashcardRead.model_validate(card)


@flashcards_router.post("/generate", response_model=GenerationJobRead, status_code=202)
async def generate_flashcards(
    payload: FlashcardGenerateRequest,
    ctx: RequestContext = Depends(require_roles(*AUTHOR_ROLES, detail=AUTHOR_DENIED)),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobRead:
    job = await FlashcardGenerationService(db).request(
        ctx.organization_id, ctx.user.id, ctx.role, payload
    )
    return GenerationJobRead.model_validate(job)


@flashcards_router.post("/{card_id}/review", response_model=FlashcardRead)
async def review_flashcard(
    card_id: UUID,
    payload: FlashcardReviewRequest,
    ctx: RequestContext = Depends(require_roles(*WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> FlashcardRead:
    card = await FlashcardService(db).review(card_id, ctx.organization_id, ctx.user.id, payload.quality)
    return FlashcardRead.model_validate(card)


@jobs_router.get("/{job_id}", response_model=GenerationJobRead)
async def get_job(
    job_id: UUID,
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobRead:
    job = await FlashcardGenerationService(db).get_job(job_id, ctx.organization_id)
    return GenerationJobRead.model_validate(job)


@progress_router.get("", response_model=ProgressRead)
async def get_progress(
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> ProgressRead:
    exams = await ExamService(db).progress(ctx.organization_id, ctx.user.id)
    cards = await FlashcardService(db).progress(ctx.organization_id, ctx.user.id)
    return merge_personal_progress(exams, cards)

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.core.files import display_name, document_kind
from app.models.document import Document, DocumentStatus
from app.models.exam import Exam, ExamKind, ExamStatus, QuestionKind
from app.models.flashcard import Flashcard


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DocumentCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = "application/pdf"
    language: str = "auto"


class DocumentRead(ORMModel):
    id: UUID
    organization_id: UUID
    owner_user_id: UUID
    filename: str
    display_title: str | None = None
    content_type: str
    status: DocumentStatus
    language: str
    page_count: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    cover_key: str | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def title(self) -> str:
        return display_name(self.display_title, self.filename)

    @computed_field
    @property
    def has_cover(self) -> bool:
        return bool(self.cover_key)

    @computed_field
    @property
    def document_kind(self) -> str:
        return document_kind(self.content_type, self.filename)


class ExamGenerateRequest(BaseModel):
    document_id: UUID
    title: str | None = Field(default=None, max_length=240)
    kind: ExamKind = ExamKind.QUIZ
    question_count: int = Field(default=10, ge=1, le=50)


class ExamCreate(ExamGenerateRequest):
    """Backwards-compatible alias used by older clients."""


class ExamRead(ORMModel):
    id: UUID
    organization_id: UUID
    owner_user_id: UUID
    document_id: UUID | None
    title: str
    kind: ExamKind
    status: ExamStatus
    time_limit_minutes: int | None
    question_count: int = 0
    generated_count: int = 0
    credit_cost: int = 0
    error_message: str | None = None
    created_at: datetime
    document_title: str | None = None
    document_kind: str | None = None
    has_cover: bool = False
    attempt_count: int = 0
    last_score: float | None = None
    last_attempt_at: datetime | None = None
    assigned_to_me: bool = False
    assignment_status: str | None = None
    assignment_count: int = 0
    assignment_completed_count: int = 0
    can_assign: bool = False


def exam_read(
    exam: Exam,
    document: Document | None = None,
    *,
    attempt_count: int = 0,
    last_score: float | None = None,
    last_attempt_at: datetime | None = None,
    assigned_to_me: bool = False,
    assignment_status: str | None = None,
    assignment_count: int = 0,
    assignment_completed_count: int = 0,
    can_assign: bool = False,
) -> ExamRead:
    payload = ExamRead.model_validate(exam)
    updates: dict = {
        "attempt_count": attempt_count,
        "last_score": last_score,
        "last_attempt_at": last_attempt_at,
        "assigned_to_me": assigned_to_me,
        "assignment_status": assignment_status,
        "assignment_count": assignment_count,
        "assignment_completed_count": assignment_completed_count,
        "can_assign": can_assign,
    }
    if document is not None:
        updates.update(
            {
                "document_title": display_name(document.display_title, document.filename),
                "document_kind": document_kind(document.content_type, document.filename),
                "has_cover": bool(document.cover_key),
            }
        )
    return payload.model_copy(update=updates)


class QuestionPublic(ORMModel):
    id: UUID
    prompt: str
    kind: QuestionKind = QuestionKind.SINGLE_CHOICE
    options: list[str]
    difficulty: str
    position: int = 0

    @field_validator("kind", mode="before")
    @classmethod
    def _parse_kind(cls, value: object) -> QuestionKind:
        return QuestionKind.parse(value)


class AttemptSummary(BaseModel):
    id: UUID
    exam_id: UUID
    score: float
    completed_at: datetime


class AssignmentRead(BaseModel):
    id: UUID
    user_id: UUID
    email: str
    full_name: str
    status: str
    completed_at: datetime | None = None
    last_score: float | None = None
    last_attempt_id: UUID | None = None


class ExamDetail(ExamRead):
    questions: list[QuestionPublic] = []
    attempts: list[AttemptSummary] = []
    assignments: list[AssignmentRead] = []
    assigned_group_ids: list[UUID] = []


class ExamAssignRequest(BaseModel):
    user_ids: list[UUID] = Field(default_factory=list)
    group_ids: list[UUID] = Field(default_factory=list)
    all_members: bool = False


class AttemptSubmit(BaseModel):
    answers: dict[str, int | list[int]] = Field(default_factory=dict)


class QuestionResult(BaseModel):
    question_id: UUID
    prompt: str
    kind: QuestionKind = QuestionKind.SINGLE_CHOICE
    options: list[str]
    selected_index: int | None = None
    selected_indices: list[int] = Field(default_factory=list)
    correct_index: int
    correct_indices: list[int] = Field(default_factory=list)
    explanation: str | None
    is_correct: bool


class AttemptRead(BaseModel):
    id: UUID
    exam_id: UUID
    user_id: UUID
    full_name: str = ""
    email: str = ""
    is_own: bool = True
    score: float
    completed_at: datetime
    results: list[QuestionResult] = []


class ProgressAttempt(BaseModel):
    id: UUID
    exam_id: UUID
    exam_title: str
    score: float
    completed_at: datetime


class ProgressRead(BaseModel):
    attempt_count: int
    exams_taken: int
    average_score: float | None
    best_score: float | None
    last_score: float | None
    recent: list[ProgressAttempt] = []
    flashcard_count: int = 0
    flashcard_due: int = 0
    flashcard_reviewed: int = 0
    flashcard_last_reviewed_at: datetime | None = None


class MemberAssignmentProgress(BaseModel):
    exam_id: UUID
    exam_title: str
    status: str
    last_score: float | None = None
    last_attempt_id: UUID | None = None
    completed_at: datetime | None = None


class MemberProgressRead(BaseModel):
    user_id: UUID
    full_name: str
    email: str
    role: str
    attempt_count: int
    exams_taken: int
    average_score: float | None
    best_score: float | None
    last_score: float | None
    assigned_count: int = 0
    assigned_pending_count: int = 0
    recent: list[ProgressAttempt] = []
    assignments: list[MemberAssignmentProgress] = []


class TeamMemberAnalytics(BaseModel):
    user_id: UUID
    full_name: str
    email: str
    role: str
    attempt_count: int
    exams_taken: int
    average_score: float | None
    assigned_count: int
    assigned_pending_count: int


class TeamExamAnalytics(BaseModel):
    exam_id: UUID
    title: str
    assigned_count: int
    completed_count: int
    average_score: float | None


class TeamRecentAttempt(BaseModel):
    id: UUID
    exam_id: UUID
    exam_title: str
    user_id: UUID
    full_name: str
    score: float
    completed_at: datetime


class TeamAnalyticsRead(BaseModel):
    member_count: int
    attempt_count: int
    exams_taken: int
    assigned_count: int
    completed_count: int
    pending_count: int
    completion_rate: float | None
    average_score: float | None
    best_score: float | None
    members: list[TeamMemberAnalytics] = []
    exams: list[TeamExamAnalytics] = []
    recent: list[TeamRecentAttempt] = []


class FlashcardCreate(BaseModel):
    front: str
    back: str
    document_id: UUID | None = None


class FlashcardGenerateRequest(BaseModel):
    document_id: UUID
    card_count: int = Field(default=12, ge=4, le=30)


class FlashcardRead(ORMModel):
    id: UUID
    organization_id: UUID
    owner_user_id: UUID
    document_id: UUID | None
    front: str
    back: str
    interval_days: int
    ease_factor: float
    repetitions: int
    next_review_at: datetime | None
    last_reviewed_at: datetime | None = None
    created_at: datetime
    document_title: str | None = None
    document_kind: str | None = None
    has_cover: bool = False
    is_due: bool = False


def flashcard_read(card: Flashcard, document: Document | None = None) -> FlashcardRead:
    now = datetime.now(timezone.utc)
    payload = FlashcardRead.model_validate(card)
    updates: dict = {
        "is_due": card.next_review_at is None or card.next_review_at <= now,
        "last_reviewed_at": card.last_reviewed_at,
    }
    if document is not None:
        updates.update(
            {
                "document_title": display_name(document.display_title, document.filename),
                "document_kind": document_kind(document.content_type, document.filename),
                "has_cover": bool(document.cover_key),
            }
        )
    return payload.model_copy(update=updates)


class FlashcardDeckRead(BaseModel):
    document_id: UUID | None
    document_title: str
    document_kind: str | None = None
    has_cover: bool = False
    card_count: int
    due_count: int
    last_reviewed_at: datetime | None = None


class FlashcardProgress(BaseModel):
    flashcard_count: int
    flashcard_due: int
    flashcard_reviewed: int
    flashcard_last_reviewed_at: datetime | None = None


class FlashcardReviewRequest(BaseModel):
    quality: int = Field(ge=0, le=5)


class GenerationJobRead(ORMModel):
    id: UUID
    organization_id: UUID
    document_id: UUID
    kind: str
    status: str
    credit_cost: int
    item_count: int
    result_id: UUID | None
    error_message: str | None
    created_at: datetime


class CreditBalanceRead(BaseModel):
    organization_id: UUID
    balance: int
    plan: str

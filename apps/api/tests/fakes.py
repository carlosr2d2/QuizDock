from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.models import Membership, MembershipRole, Organization, PlanTier, User
from app.models.document import Document, DocumentStatus
from app.models.exam import Exam, ExamAssignment, ExamKind, ExamStatus, Question
from app.models.mixins import utcnow


def now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_id(entity) -> None:
    if getattr(entity, "id", None) is None:
        entity.id = uuid4()
    if getattr(entity, "created_at", None) is None:
        entity.created_at = now()
    if getattr(entity, "updated_at", None) is None:
        entity.updated_at = entity.created_at


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def add(self, item: object) -> None:
        self.added.append(item)

    async def commit(self) -> None:
        self.commits += 1

    async def flush(self) -> None:
        return None

    async def refresh(self, item: object) -> None:
        ensure_id(item)


class FakeUserRepo:
    def __init__(self) -> None:
        self.by_id: dict[UUID, User] = {}
        self.by_email: dict[str, User] = {}

    async def add(self, user: User) -> User:
        ensure_id(user)
        if not hasattr(user, "memberships") or user.memberships is None:
            user.memberships = []
        self.by_id[user.id] = user
        self.by_email[user.email] = user
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.by_id.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return self.by_email.get(email)


class FakeOrgRepo:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Organization] = {}
        self.slugs: set[str] = set()

    async def add(self, org: Organization) -> Organization:
        ensure_id(org)
        self.by_id[org.id] = org
        self.slugs.add(org.slug)
        return org

    async def get(self, organization_id: UUID) -> Organization | None:
        return self.by_id.get(organization_id)

    async def get_for_update(self, organization_id: UUID) -> Organization | None:
        return self.by_id.get(organization_id)

    async def slug_exists(self, slug: str) -> bool:
        return slug in self.slugs


class FakeMembershipRepo:
    def __init__(self) -> None:
        self.items: list[Membership] = []

    async def add(self, membership: Membership) -> Membership:
        ensure_id(membership)
        self.items.append(membership)
        return membership

    async def list_with_users(self, organization_id: UUID) -> list[Membership]:
        return [item for item in self.items if item.organization_id == organization_id]

    async def get(self, user_id: UUID, organization_id: UUID) -> Membership | None:
        for item in self.items:
            if item.user_id == user_id and item.organization_id == organization_id:
                return item
        return None

    async def get_with_user(self, user_id: UUID, organization_id: UUID) -> Membership | None:
        return await self.get(user_id, organization_id)


class FakeTxRepo:
    def __init__(self) -> None:
        self.items: list[object] = []

    async def add_transaction(self, transaction: object) -> object:
        ensure_id(transaction)
        self.items.append(transaction)
        return transaction


class FakeDocumentRepo:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Document] = {}

    async def add(self, document: Document) -> Document:
        ensure_id(document)
        self.by_id[document.id] = document
        return document

    async def get(self, document_id: UUID, organization_id: UUID) -> Document | None:
        document = self.by_id.get(document_id)
        if document is None or document.organization_id != organization_id:
            return None
        return document

    async def get_by_id(self, document_id: UUID | None) -> Document | None:
        if document_id is None:
            return None
        return self.by_id.get(document_id)

    async def get_many(self, ids: set[UUID], organization_id: UUID) -> dict[UUID, Document]:
        return {
            item.id: item
            for item in self.by_id.values()
            if item.id in ids and item.organization_id == organization_id
        }


class FakeExamRepo:
    def __init__(self) -> None:
        self.exams: list[Exam] = []
        self.questions: list[Question] = []
        self.assignments: list[ExamAssignment] = []
        self.attempts: list[object] = []
        self.people: dict[UUID, User] = {}

    async def add(self, exam: Exam) -> Exam:
        ensure_id(exam)
        if not hasattr(exam, "questions") or exam.questions is None:
            exam.questions = []
        self.exams.append(exam)
        return exam

    async def get(self, exam_id: UUID, organization_id: UUID) -> Exam | None:
        for exam in self.exams:
            if exam.id == exam_id and exam.organization_id == organization_id:
                return exam
        return None

    async def get_by_id(self, exam_id: UUID) -> Exam | None:
        for exam in self.exams:
            if exam.id == exam_id:
                return exam
        return None

    async def add_questions(self, questions: list[Question]) -> None:
        for question in questions:
            ensure_id(question)
            self.questions.append(question)
            for exam in self.exams:
                if exam.id == question.exam_id:
                    exam.questions.append(question)

    async def used_chunk_positions(self, document_id: UUID, organization_id: UUID) -> set[int]:
        return set()

    async def get_assignment(
        self, exam_id: UUID, user_id: UUID, organization_id: UUID
    ) -> ExamAssignment | None:
        for item in self.assignments:
            if (
                item.exam_id == exam_id
                and item.user_id == user_id
                and item.organization_id == organization_id
            ):
                return item
        return None

    async def add_assignment(self, assignment: ExamAssignment) -> ExamAssignment:
        ensure_id(assignment)
        self.assignments.append(assignment)
        return assignment

    async def list_assignments(self, exam_id: UUID, organization_id: UUID) -> list[ExamAssignment]:
        return [
            item
            for item in self.assignments
            if item.exam_id == exam_id and item.organization_id == organization_id
        ]

    async def list_assignments_for_user_with_titles(
        self, organization_id: UUID, user_id: UUID
    ) -> list[tuple[ExamAssignment, str]]:
        rows: list[tuple[ExamAssignment, str]] = []
        for item in self.assignments:
            if item.organization_id != organization_id or item.user_id != user_id:
                continue
            exam = next((row for row in self.exams if row.id == item.exam_id), None)
            rows.append((item, exam.title if exam else "Examen"))
        return rows

    async def add_attempt(self, attempt: object) -> object:
        ensure_id(attempt)
        self.attempts.append(attempt)
        return attempt

    async def progress_aggregates(
        self, organization_id: UUID, user_id: UUID
    ) -> tuple[int, int, float | None, float | None]:
        attempts = [
            item
            for item in self.attempts
            if getattr(item, "organization_id", None) == organization_id
            and getattr(item, "user_id", None) == user_id
            and getattr(item, "completed_at", None) is not None
        ]
        if not attempts:
            return 0, 0, None, None
        scores = [float(item.score) for item in attempts if getattr(item, "score", None) is not None]
        exam_ids = {item.exam_id for item in attempts}
        average = sum(scores) / len(scores) if scores else None
        best = max(scores) if scores else None
        return len(attempts), len(exam_ids), average, best

    async def recent_attempts(
        self, organization_id: UUID, user_id: UUID, limit: int = 8
    ) -> list[tuple[object, str]]:
        attempts = [
            item
            for item in self.attempts
            if getattr(item, "organization_id", None) == organization_id
            and getattr(item, "user_id", None) == user_id
            and getattr(item, "completed_at", None) is not None
        ]
        attempts.sort(key=lambda item: item.completed_at, reverse=True)
        rows: list[tuple[object, str]] = []
        for item in attempts[:limit]:
            exam = next((row for row in self.exams if row.id == item.exam_id), None)
            rows.append((item, exam.title if exam else "Examen"))
        return rows

    async def users_by_ids(self, ids: set[UUID]) -> dict[UUID, User]:
        return {user_id: user for user_id, user in self.people.items() if user_id in ids}

    async def latest_attempts(
        self, exam_id: UUID, organization_id: UUID, user_ids: set[UUID]
    ) -> dict[UUID, tuple[float | None, UUID | None]]:
        empty: dict[UUID, tuple[float | None, UUID | None]] = {user_id: (None, None) for user_id in user_ids}
        for item in self.attempts:
            if (
                getattr(item, "exam_id", None) == exam_id
                and getattr(item, "organization_id", None) == organization_id
                and getattr(item, "user_id", None) in user_ids
                and getattr(item, "completed_at", None) is not None
            ):
                empty[item.user_id] = (item.score, item.id)
        return empty


def make_user(
    *,
    email: str = "demo@example.com",
    full_name: str = "Demo User",
    password_hash: str = "hashed",
    is_active: bool = True,
    personal_organization_id: UUID | None = None,
) -> User:
    user = User(
        id=uuid4(),
        email=email,
        hashed_password=password_hash,
        full_name=full_name,
        is_active=is_active,
        personal_organization_id=personal_organization_id,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    user.memberships = []
    return user


def make_org(
    *,
    name: str = "Demo workspace",
    slug: str = "demo-workspace",
    credit_balance: int = 50,
    is_personal: bool = True,
    plan: PlanTier = PlanTier.FREE,
) -> Organization:
    return Organization(
        id=uuid4(),
        name=name,
        slug=slug,
        plan=plan,
        is_personal=is_personal,
        credit_balance=credit_balance,
        created_at=utcnow(),
        updated_at=utcnow(),
    )


def make_document(
    organization_id: UUID,
    owner_user_id: UUID,
    *,
    status: DocumentStatus = DocumentStatus.READY,
    extracted_text: str | None = "El documento describe el modelo de tenancy.",
    filename: str = "guia.pdf",
) -> Document:
    return Document(
        id=uuid4(),
        organization_id=organization_id,
        owner_user_id=owner_user_id,
        filename=filename,
        display_title="Guía",
        content_type="application/pdf",
        storage_key="docs/guia.pdf",
        status=status,
        language="es",
        extracted_text=extracted_text,
        created_at=utcnow(),
        updated_at=utcnow(),
    )


def make_exam(
    organization_id: UUID,
    owner_user_id: UUID,
    document_id: UUID | None,
    *,
    status: ExamStatus = ExamStatus.GENERATING,
    question_count: int = 8,
    credit_cost: int = 8,
) -> Exam:
    exam = Exam(
        id=uuid4(),
        organization_id=organization_id,
        owner_user_id=owner_user_id,
        document_id=document_id,
        title="Examen",
        kind=ExamKind.QUIZ,
        status=status,
        question_count=question_count,
        generated_count=0,
        credit_cost=credit_cost,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    exam.questions = []
    return exam


def make_membership(
    user: User,
    organization_id: UUID,
    role: MembershipRole = MembershipRole.MEMBER,
) -> Membership:
    membership = Membership(
        id=uuid4(),
        user_id=user.id,
        organization_id=organization_id,
        role=role,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    membership.user = user
    return membership

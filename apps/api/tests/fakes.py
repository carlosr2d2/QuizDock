from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.models import Invitation, Membership, MembershipRole, Organization, PasswordResetToken, PlanTier, User
from app.models.billing import PaymentOrder, PaymentStatus
from app.models.document import Document, DocumentStatus
from app.models.exam import Exam, ExamAssignment, ExamKind, ExamStatus, Question, QuestionKind
from app.models.identity import InvitationStatus
from app.models.mixins import utcnow
from app.services.mail import OutboundEmail


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


class FakeAuditService:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def record(self, organization_id, action, **kwargs):
        event = {
            "organization_id": organization_id,
            "action": action,
            **kwargs,
        }
        self.events.append(event)
        return event

    async def list_events(self, organization_id, role, *, limit: int = 50, offset: int = 0):
        from app.schemas.audit import AuditEventList

        return AuditEventList(items=[], total=0, limit=limit, offset=offset)


class FakeAuditRepo:
    def __init__(self) -> None:
        self.items: list = []

    async def add(self, event):
        ensure_id(event)
        if getattr(event, "payload", None) is None:
            event.payload = {}
        self.items.append(event)
        return event

    async def list_for_org(self, organization_id: UUID, *, limit: int = 50, offset: int = 0):
        rows = [item for item in self.items if item.organization_id == organization_id]
        rows.sort(key=lambda item: item.created_at, reverse=True)
        sliced = rows[offset : offset + limit]
        return [(item, None, None) for item in sliced], len(rows)


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

    async def delete(self, membership: Membership) -> None:
        self.items = [item for item in self.items if item is not membership and item.id != membership.id]


class FakeGroupRepo:
    def __init__(self) -> None:
        self.groups: list = []
        self.members: list = []

    async def add(self, group):
        ensure_id(group)
        if not hasattr(group, "members") or group.members is None:
            group.members = []
        self.groups.append(group)
        return group

    async def get(self, group_id: UUID, organization_id: UUID):
        for group in self.groups:
            if group.id == group_id and group.organization_id == organization_id:
                return group
        return None

    async def get_by_name(self, organization_id: UUID, name: str):
        for group in self.groups:
            if group.organization_id == organization_id and group.name == name:
                return group
        return None

    async def list_for_org(self, organization_id: UUID):
        return [group for group in self.groups if group.organization_id == organization_id]

    async def delete(self, group) -> None:
        self.groups = [item for item in self.groups if item.id != group.id]
        self.members = [item for item in self.members if item.group_id != group.id]
        group.members = []

    async def add_member(self, member):
        ensure_id(member)
        self.members.append(member)
        for group in self.groups:
            if group.id == member.group_id:
                group.members.append(member)
        return member

    async def get_member(self, group_id: UUID, user_id: UUID, organization_id: UUID):
        for item in self.members:
            if (
                item.group_id == group_id
                and item.user_id == user_id
                and item.organization_id == organization_id
            ):
                return item
        return None

    async def delete_member(self, member) -> None:
        self.members = [item for item in self.members if item.id != member.id]
        for group in self.groups:
            if group.id == member.group_id:
                group.members = [item for item in group.members if item.id != member.id]

    async def member_user_ids(self, group_id: UUID, organization_id: UUID) -> set[UUID]:
        return {
            item.user_id
            for item in self.members
            if item.group_id == group_id and item.organization_id == organization_id
        }

    async def delete_user_from_org(self, organization_id: UUID, user_id: UUID) -> None:
        remaining = []
        for item in self.members:
            if item.organization_id == organization_id and item.user_id == user_id:
                for group in self.groups:
                    if group.id == item.group_id:
                        group.members = [row for row in group.members if row.id != item.id]
                continue
            remaining.append(item)
        self.members = remaining

    async def replace_members(self, group, organization_id: UUID, user_ids: set[UUID]) -> None:
        from app.models.group import GroupMember

        current = {item.user_id: item for item in list(group.members)}
        for user_id, item in current.items():
            if user_id not in user_ids:
                await self.delete_member(item)
        for user_id in user_ids:
            if user_id in current:
                continue
            await self.add_member(
                GroupMember(organization_id=organization_id, group_id=group.id, user_id=user_id)
            )


class FakeInvitationRepo:
    def __init__(self) -> None:
        self.items: list[Invitation] = []

    async def add(self, invitation: Invitation) -> Invitation:
        ensure_id(invitation)
        self.items.append(invitation)
        return invitation

    async def get(self, invitation_id: UUID, organization_id: UUID) -> Invitation | None:
        return next(
            (
                item
                for item in self.items
                if item.id == invitation_id and item.organization_id == organization_id
            ),
            None,
        )

    async def get_by_token(self, token: str) -> Invitation | None:
        return next((item for item in self.items if item.token == token), None)

    async def get_pending(self, organization_id: UUID, email: str) -> Invitation | None:
        return next(
            (
                item
                for item in self.items
                if item.organization_id == organization_id
                and item.email.lower() == email.lower()
                and item.status == InvitationStatus.PENDING
            ),
            None,
        )

    async def list_for_org(self, organization_id: UUID) -> list[Invitation]:
        return [item for item in self.items if item.organization_id == organization_id]

    async def list_pending_for_email(self, email: str) -> list[Invitation]:
        return [
            item
            for item in self.items
            if item.email.lower() == email.lower() and item.status == InvitationStatus.PENDING
        ]


class FakeMailer:
    def __init__(self, *, configured: bool = True) -> None:
        self.configured = configured
        self.sent: list[OutboundEmail] = []
        self.error: Exception | None = None

    def send(self, message: OutboundEmail) -> None:
        if self.error:
            raise self.error
        self.sent.append(message)


class FakePasswordResetRepo:
    def __init__(self) -> None:
        self.items: list[PasswordResetToken] = []

    async def add(self, token: PasswordResetToken) -> PasswordResetToken:
        ensure_id(token)
        self.items.append(token)
        return token

    async def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        return next((item for item in self.items if item.token_hash == token_hash), None)

    async def expire_unused_for_user(self, user_id: UUID, except_id: UUID | None = None) -> None:
        stamp = now()
        for item in self.items:
            if item.user_id == user_id and item.used_at is None and item.id != except_id:
                item.used_at = stamp


class FakeTxRepo:
    def __init__(self) -> None:
        self.items: list[object] = []

    async def add_transaction(self, transaction: object) -> object:
        ensure_id(transaction)
        self.items.append(transaction)
        return transaction

    async def list_for_org(self, organization_id: UUID, *, limit: int = 40) -> list:
        matches = [item for item in self.items if getattr(item, "organization_id", None) == organization_id]
        return matches[:limit]


class FakePaymentOrderRepo:
    def __init__(self) -> None:
        self.items: list[PaymentOrder] = []

    async def add(self, order: PaymentOrder) -> PaymentOrder:
        ensure_id(order)
        if order.status is None:
            order.status = PaymentStatus.PENDING
        if getattr(order, "kind", None) is None:
            order.kind = "pack"
        self.items.append(order)
        return order

    async def get(self, order_id: UUID, organization_id: UUID | None = None) -> PaymentOrder | None:
        for item in self.items:
            if item.id != order_id:
                continue
            if organization_id is not None and item.organization_id != organization_id:
                return None
            return item
        return None

    async def get_for_update(self, order_id: UUID) -> PaymentOrder | None:
        return await self.get(order_id)

    async def get_by_provider_session(self, provider: str, provider_session_id: str) -> PaymentOrder | None:
        return next(
            (
                item
                for item in self.items
                if item.provider == provider and item.provider_session_id == provider_session_id
            ),
            None,
        )

    async def list_for_org(self, organization_id: UUID, *, limit: int = 40) -> list[PaymentOrder]:
        return [item for item in self.items if item.organization_id == organization_id][:limit]


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

    async def delete(self, document: Document) -> None:
        self.by_id.pop(document.id, None)


class FakeExamRepo:
    def __init__(self) -> None:
        self.exams: list[Exam] = []
        self.questions: list[Question] = []
        self.assignments: list[ExamAssignment] = []
        self.group_assignments: list = []
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

    async def weak_exam_aggregates(
        self,
        organization_id: UUID,
        user_id: UUID,
        *,
        limit: int = 8,
    ) -> list[tuple[UUID, str, float, int]]:
        grouped: dict[UUID, list[float]] = {}
        for item in self.attempts:
            if (
                getattr(item, "organization_id", None) != organization_id
                or getattr(item, "user_id", None) != user_id
                or getattr(item, "completed_at", None) is None
                or getattr(item, "score", None) is None
            ):
                continue
            grouped.setdefault(item.exam_id, []).append(float(item.score))
        rows: list[tuple[UUID, str, float, int]] = []
        for exam_id, scores in grouped.items():
            exam = next(
                (
                    row
                    for row in self.exams
                    if row.id == exam_id and row.organization_id == organization_id
                ),
                None,
            )
            if exam is None:
                continue
            rows.append((exam_id, exam.title, sum(scores) / len(scores), len(scores)))
        rows.sort(key=lambda item: (item[2], -item[3]))
        return rows[:limit]

    async def questions_for_exams(
        self, exam_ids: set[UUID], organization_id: UUID
    ) -> list[Question]:
        allowed = {
            exam.id
            for exam in self.exams
            if exam.id in exam_ids and exam.organization_id == organization_id
        }
        seen: set[UUID] = set()
        out: list[Question] = []
        for exam in self.exams:
            if exam.id not in allowed:
                continue
            for question in exam.questions or []:
                if question.id in seen:
                    continue
                seen.add(question.id)
                out.append(question)
        for question in self.questions:
            if question.exam_id not in allowed or question.id in seen:
                continue
            seen.add(question.id)
            out.append(question)
        return out

    async def completed_at_times(
        self, organization_id: UUID, user_id: UUID
    ) -> list[datetime]:
        return [
            item.completed_at
            for item in self.attempts
            if getattr(item, "organization_id", None) == organization_id
            and getattr(item, "user_id", None) == user_id
            and getattr(item, "completed_at", None) is not None
        ]

    async def org_progress_aggregates(
        self, organization_id: UUID
    ) -> tuple[int, int, float | None, float | None]:
        attempts = [
            item
            for item in self.attempts
            if getattr(item, "organization_id", None) == organization_id
            and getattr(item, "completed_at", None) is not None
        ]
        if not attempts:
            return 0, 0, None, None
        scores = [float(item.score) for item in attempts if getattr(item, "score", None) is not None]
        exam_ids = {item.exam_id for item in attempts}
        average = sum(scores) / len(scores) if scores else None
        best = max(scores) if scores else None
        return len(attempts), len(exam_ids), average, best

    async def progress_by_user(
        self, organization_id: UUID
    ) -> dict[UUID, tuple[int, int, float | None]]:
        grouped: dict[UUID, list] = {}
        for item in self.attempts:
            if (
                getattr(item, "organization_id", None) != organization_id
                or getattr(item, "completed_at", None) is None
            ):
                continue
            grouped.setdefault(item.user_id, []).append(item)
        out: dict[UUID, tuple[int, int, float | None]] = {}
        for user_id, items in grouped.items():
            scores = [float(row.score) for row in items if getattr(row, "score", None) is not None]
            out[user_id] = (
                len(items),
                len({row.exam_id for row in items}),
                sum(scores) / len(scores) if scores else None,
            )
        return out

    def _assignment_completed(self, item: ExamAssignment) -> bool:
        status = item.status.value if hasattr(item.status, "value") else str(item.status)
        return status.rsplit(".", 1)[-1].lower() == "completed"

    async def org_assignment_totals(self, organization_id: UUID) -> tuple[int, int]:
        rows = [item for item in self.assignments if item.organization_id == organization_id]
        completed = sum(1 for item in rows if self._assignment_completed(item))
        return len(rows), completed

    async def assignment_totals_by_user(self, organization_id: UUID) -> dict[UUID, tuple[int, int]]:
        out: dict[UUID, tuple[int, int]] = {}
        for item in self.assignments:
            if item.organization_id != organization_id:
                continue
            total, pending = out.get(item.user_id, (0, 0))
            total += 1
            if not self._assignment_completed(item):
                pending += 1
            out[item.user_id] = (total, pending)
        return out

    async def assigned_exam_counts(
        self, organization_id: UUID
    ) -> list[tuple[UUID, str, int, int]]:
        by_exam: dict[UUID, tuple[str, int, int]] = {}
        for item in self.assignments:
            if item.organization_id != organization_id:
                continue
            exam = next((row for row in self.exams if row.id == item.exam_id), None)
            title, total, done = by_exam.get(item.exam_id, (exam.title if exam else "Examen", 0, 0))
            total += 1
            if self._assignment_completed(item):
                done += 1
            by_exam[item.exam_id] = (title, total, done)
        return [(exam_id, title, total, done) for exam_id, (title, total, done) in by_exam.items()]

    async def exam_score_averages(self, organization_id: UUID) -> dict[UUID, float]:
        grouped: dict[UUID, list[float]] = {}
        for item in self.attempts:
            if (
                getattr(item, "organization_id", None) != organization_id
                or getattr(item, "completed_at", None) is None
                or getattr(item, "score", None) is None
            ):
                continue
            grouped.setdefault(item.exam_id, []).append(float(item.score))
        return {exam_id: sum(scores) / len(scores) for exam_id, scores in grouped.items()}

    async def recent_attempts_for_org(
        self, organization_id: UUID, limit: int = 12
    ) -> list[tuple[object, str, str]]:
        attempts = [
            item
            for item in self.attempts
            if getattr(item, "organization_id", None) == organization_id
            and getattr(item, "completed_at", None) is not None
        ]
        attempts.sort(key=lambda item: item.completed_at, reverse=True)
        rows: list[tuple[object, str, str]] = []
        for item in attempts[:limit]:
            exam = next((row for row in self.exams if row.id == item.exam_id), None)
            person = self.people.get(item.user_id)
            rows.append((item, exam.title if exam else "Examen", person.full_name if person else ""))
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

    async def get_exam_group_assignment(self, exam_id: UUID, group_id: UUID, organization_id: UUID):
        for item in self.group_assignments:
            if (
                item.exam_id == exam_id
                and item.group_id == group_id
                and item.organization_id == organization_id
            ):
                return item
        return None

    async def add_exam_group_assignment(self, assignment):
        ensure_id(assignment)
        self.group_assignments.append(assignment)
        return assignment

    async def list_exam_group_ids(self, exam_id: UUID, organization_id: UUID) -> list[UUID]:
        return [
            item.group_id
            for item in self.group_assignments
            if item.exam_id == exam_id and item.organization_id == organization_id
        ]

    async def stats_for_exams(self, exam_ids, organization_id, user_id):
        from app.repositories.content import ExamAttemptStats

        return {exam_id: ExamAttemptStats() for exam_id in exam_ids}

    async def assignment_counts(self, exam_ids, organization_id):
        return {exam_id: (0, 0) for exam_id in exam_ids}

    async def list_attempts(self, exam_id, organization_id, user_id):
        return [
            item
            for item in self.attempts
            if getattr(item, "exam_id", None) == exam_id
            and getattr(item, "user_id", None) == user_id
        ]


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
    plan: PlanTier | None = None,
    billing_country: str = "CO",
    plan_sku: str | None = None,
    plan_renews_at=None,
) -> Organization:
    resolved_plan = plan if plan is not None else (PlanTier.FREE if is_personal else PlanTier.TEAM)
    return Organization(
        id=uuid4(),
        name=name,
        slug=slug,
        plan=resolved_plan,
        is_personal=is_personal,
        credit_balance=credit_balance,
        billing_country=billing_country,
        plan_sku=plan_sku,
        plan_renews_at=plan_renews_at,
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
    allow_pdf_download: bool = False,
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
        allow_pdf_download=allow_pdf_download,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    exam.questions = []
    return exam


def make_question(
    exam_id: UUID,
    *,
    prompt: str = "¿Correcto?",
    kind: QuestionKind = QuestionKind.SINGLE_CHOICE,
    options: list[str] | None = None,
    correct_index: int = 0,
    correct_indices: list[int] | None = None,
    position: int = 0,
) -> Question:
    return Question(
        id=uuid4(),
        exam_id=exam_id,
        prompt=prompt,
        kind=kind,
        options=options or ["A", "B", "C", "D"],
        correct_index=correct_index,
        correct_indices=correct_indices if correct_indices is not None else [correct_index],
        difficulty="medium",
        position=position,
        created_at=utcnow(),
        updated_at=utcnow(),
    )


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

from datetime import date, datetime, timedelta, timezone
from collections.abc import Iterable

from app.schemas.content import FlashcardProgress, ProgressRead

WEAK_AVERAGE_THRESHOLD = 80.0
TREND_LIMIT = 12
KIND_ACCURACY_ATTEMPT_LIMIT = 50
MASTERED_INTERVAL_DAYS = 21


def as_utc_date(value: datetime) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).date()


def consecutive_streak(dates: Iterable[date], today: date | None = None) -> int:
    unique = {item for item in dates if item is not None}
    if not unique:
        return 0
    cursor = today or datetime.now(timezone.utc).date()
    if cursor not in unique:
        cursor = cursor - timedelta(days=1)
        if cursor not in unique:
            return 0
    streak = 0
    while cursor in unique:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def merge_personal_progress(exams: ProgressRead, cards: FlashcardProgress) -> ProgressRead:
    dates = [*exams.study_dates, *cards.study_dates]
    payload = cards.model_dump()
    return exams.model_copy(
        update={
            **payload,
            "study_streak_days": consecutive_streak(dates),
        }
    )

"""Plan an exam as a whole: kind mix, unique chunks, and a focus per item."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.exam import QuestionKind
from app.services.exam_quality import polish_exam_text
from app.services.rag import RetrievedContext

_STYLES = (
    "definición: el alumno debe reconocer un concepto clave con sus propias palabras",
    "aplicación: el alumno debe identificar un uso o caso práctico",
    "causalidad: el alumno debe relacionar una causa, un paso o una consecuencia",
    "contraste: el alumno debe distinguir dos ideas próximas",
    "comprensión: el alumno identifica el concepto a partir de una descripción breve",
)

_KIND_ORDER = (
    QuestionKind.SINGLE_CHOICE,
    QuestionKind.TRUE_FALSE,
    QuestionKind.MULTIPLE_CHOICE,
)


@dataclass(frozen=True)
class ExamSlot:
    context: RetrievedContext | str
    kind: QuestionKind
    style: str
    focus: str


def kind_plan(count: int) -> list[QuestionKind]:
    """About half single-choice, a quarter true/false, a quarter multi-select."""
    if count <= 0:
        return []
    if count == 1:
        return [QuestionKind.SINGLE_CHOICE]
    if count == 2:
        return [QuestionKind.SINGLE_CHOICE, QuestionKind.TRUE_FALSE]
    multi = max(1, round(count * 0.25))
    true_false = max(1, round(count * 0.25))
    single = count - multi - true_false
    if single < 1:
        single = 1
        if true_false >= multi and true_false > 1:
            true_false -= 1
        elif multi > 1:
            multi -= 1
    buckets = {
        QuestionKind.SINGLE_CHOICE: [QuestionKind.SINGLE_CHOICE] * single,
        QuestionKind.TRUE_FALSE: [QuestionKind.TRUE_FALSE] * true_false,
        QuestionKind.MULTIPLE_CHOICE: [QuestionKind.MULTIPLE_CHOICE] * multi,
    }
    plan: list[QuestionKind] = []
    while any(buckets.values()):
        for kind in _KIND_ORDER:
            if buckets[kind]:
                plan.append(buckets[kind].pop(0))
    return plan[:count]


def chunk_focus(content: str, limit: int = 90) -> str:
    text = polish_exam_text(content or "")
    first = re.split(r"(?<=[\.\!\?])\s+", text, maxsplit=1)[0].strip()
    if len(first) > limit:
        first = first[:limit].rsplit(" ", 1)[0].rstrip(".,;:")
    return first


def _context_key(item: RetrievedContext | str) -> str:
    if isinstance(item, RetrievedContext):
        return f"{item.position}:{item.content[:80]}"
    return item[:80]


def build_exam_blueprint(
    contexts: list[RetrievedContext] | list[str],
    question_count: int,
) -> list[ExamSlot]:
    """One slot per planned item, unique chunks first, rotating style."""
    if not contexts or question_count <= 0:
        return []
    unique: list[RetrievedContext | str] = []
    seen: set[str] = set()
    for item in contexts:
        key = _context_key(item)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    ordered = unique or list(contexts)
    kinds = kind_plan(question_count)
    slots: list[ExamSlot] = []
    for index, kind in enumerate(kinds):
        item = ordered[index % len(ordered)]
        content = item.content if isinstance(item, RetrievedContext) else item
        slots.append(
            ExamSlot(
                context=item,
                kind=kind,
                style=_STYLES[index % len(_STYLES)],
                focus=chunk_focus(content),
            )
        )
    return slots


def prompt_fingerprint(prompt: str) -> str:
    return re.sub(r"\W+", "", (prompt or "").lower())[:80]


def select_diverse_questions(candidates: list, target: int) -> list:
    """Keep planned kind coverage, then fill remaining good items."""
    if target <= 0 or not candidates:
        return []
    planned = kind_plan(target)
    remaining = list(candidates)
    chosen: list = []
    seen: set[str] = set()

    def take(predicate) -> bool:
        for index, question in enumerate(remaining):
            key = prompt_fingerprint(getattr(question, "prompt", ""))
            if key in seen:
                continue
            if predicate(question):
                chosen.append(remaining.pop(index))
                seen.add(key)
                return True
        return False

    for kind in planned:
        take(lambda question, expected=kind: question.kind == expected)
        if len(chosen) >= target:
            return chosen[:target]
    while len(chosen) < target and take(lambda _question: True):
        pass
    return chosen[:target]

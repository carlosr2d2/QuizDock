import pytest

from app.models.exam import QuestionKind
from app.services.exam_blueprint import (
    build_exam_blueprint,
    chunk_focus,
    kind_plan,
    select_diverse_questions,
)
from app.services.llm import GeneratedExam, GeneratedQuestion, generate_exam_from_contexts
from app.services.rag import RetrievedContext


def test_kind_plan_balances_ten_questions():
    plan = kind_plan(10)
    assert len(plan) == 10
    assert plan.count(QuestionKind.SINGLE_CHOICE) == 6
    assert plan.count(QuestionKind.TRUE_FALSE) == 2
    assert plan.count(QuestionKind.MULTIPLE_CHOICE) == 2
    assert plan[0] is QuestionKind.SINGLE_CHOICE
    assert QuestionKind.TRUE_FALSE in plan[:4]
    assert QuestionKind.MULTIPLE_CHOICE in plan[:4]


def test_blueprint_uses_unique_chunks_before_repeating():
    contexts = [
        RetrievedContext(position=index, content=f"Hecho concreto número {index} sobre el tema.")
        for index in range(4)
    ]
    slots = build_exam_blueprint(contexts, 4)
    assert len(slots) == 4
    positions = [
        slot.context.position if isinstance(slot.context, RetrievedContext) else -1 for slot in slots
    ]
    assert positions == [0, 1, 2, 3]
    assert slots[0].kind is QuestionKind.SINGLE_CHOICE
    assert all(slot.focus for slot in slots)


def test_chunk_focus_takes_first_sentence():
    focus = chunk_focus("Playground AI genera imágenes. Luego aparece otra idea larga.")
    assert focus.startswith("Playground AI")
    assert "Luego" not in focus


def test_select_diverse_keeps_kind_mix():
    candidates = [
        GeneratedQuestion(
            prompt="¿Qué es el tenancy?",
            options=["A", "B", "C", "D"],
            correct_index=0,
            kind=QuestionKind.SINGLE_CHOICE,
        ),
        GeneratedQuestion(
            prompt="El worker descuenta créditos al generar.",
            options=["Verdadero", "Falso"],
            correct_index=0,
            kind=QuestionKind.TRUE_FALSE,
        ),
        GeneratedQuestion(
            prompt="¿Cuáles roles aplican?",
            options=["A", "B", "C", "D"],
            correct_indices=[0, 1],
            kind=QuestionKind.MULTIPLE_CHOICE,
        ),
        GeneratedQuestion(
            prompt="¿Qué hace Celery?",
            options=["A", "B", "C", "D"],
            correct_index=0,
            kind=QuestionKind.SINGLE_CHOICE,
        ),
    ]
    chosen = select_diverse_questions(candidates, 3)
    kinds = {item.kind for item in chosen}
    assert kinds == {
        QuestionKind.SINGLE_CHOICE,
        QuestionKind.TRUE_FALSE,
        QuestionKind.MULTIPLE_CHOICE,
    }


def _stub_question(kind: QuestionKind, focus: str) -> GeneratedQuestion:
    if kind is QuestionKind.TRUE_FALSE:
        prompt = f"Playground AI {focus[:40]}."
        options = ["Verdadero", "Falso"]
    else:
        prompt = f"¿Qué cubre este tramo sobre {focus[:40]}?"
        options = ["A", "B", "C", "D"]
    return GeneratedQuestion(
        prompt=prompt,
        options=options,
        correct_index=0,
        kind=kind,
        claim=focus,
        anchor="",
    )


@pytest.mark.asyncio
async def test_generate_exam_from_contexts_uses_blueprint_and_persists_selection(monkeypatch):
    calls: list[tuple[QuestionKind, str]] = []
    persisted: list[GeneratedQuestion] = []

    async def fake_payload(text, count, language, *, style, kind, subject="", focus="", rewrite=False):
        calls.append((kind, focus))
        return GeneratedExam(title=subject, questions=[_stub_question(kind, focus or text)])

    monkeypatch.setattr("app.services.llm.generate_exam_payload", fake_payload)

    contexts = [
        RetrievedContext(position=0, content="Playground AI genera imágenes a partir de texto."),
        RetrievedContext(position=1, content="El espacio latente agrupa conceptos cercanos."),
        RetrievedContext(position=2, content="Los créditos se descuentan al generar el examen."),
        RetrievedContext(position=3, content="Celery procesa PDFs fuera de la petición HTTP."),
    ]

    async def persist(item: GeneratedQuestion) -> None:
        persisted.append(item)

    progress: list[tuple[int, int]] = []

    async def report(current: int, total: int) -> None:
        progress.append((current, total))

    exam = await generate_exam_from_contexts(
        contexts,
        4,
        "es",
        "Playground AI",
        on_question=persist,
        on_progress=report,
    )
    assert len(exam.questions) == 4
    assert len(persisted) == 4
    assert len(calls) == 8
    assert progress
    assert progress[0][0] >= 1
    assert progress[-1] == (4, 4)
    kinds = {item.kind for item in exam.questions}
    assert QuestionKind.SINGLE_CHOICE in kinds
    assert QuestionKind.TRUE_FALSE in kinds
    assert QuestionKind.MULTIPLE_CHOICE in kinds
    focuses = {focus for _kind, focus in calls}
    assert any("Playground AI" in focus for focus in focuses)
    assert any("espacio latente" in focus for focus in focuses)

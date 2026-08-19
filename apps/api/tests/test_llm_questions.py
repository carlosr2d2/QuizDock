import pytest

from app.models.exam import QuestionKind
from app.services.llm import (
    GeneratedQuestion,
    HeuristicClient,
    coerce_question_kind,
    _heuristic_question,
)


SENTENCES = [
    "La inteligencia artificial genera texto a partir de modelos entrenados con datos.",
    "El procesamiento asíncrono evita bloquear la API durante la generación.",
    "Los workspaces personales y de empresa comparten el mismo modelo de tenancy.",
    "Los créditos se descuentan cuando el worker crea preguntas o flashcards.",
]


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (QuestionKind.TRUE_FALSE, QuestionKind.TRUE_FALSE),
        (QuestionKind.SINGLE_CHOICE, QuestionKind.SINGLE_CHOICE),
        (QuestionKind.MULTIPLE_CHOICE, QuestionKind.MULTIPLE_CHOICE),
    ],
)
def test_heuristic_question_emits_requested_kind(kind: QuestionKind, expected: QuestionKind):
    payload = _heuristic_question(SENTENCES, 0, kind, "es")
    question = GeneratedQuestion.model_validate(payload)
    assert question.kind is expected
    assert question.correct_indices
    assert all(0 <= index < len(question.options) for index in question.correct_indices)


def test_heuristic_true_false_uses_spanish_labels():
    payload = _heuristic_question(SENTENCES, 0, QuestionKind.TRUE_FALSE, "es")
    assert payload["options"] == ["Verdadero", "Falso"]


def test_heuristic_multiple_choice_has_several_correct_answers():
    payload = _heuristic_question(SENTENCES, 0, QuestionKind.MULTIPLE_CHOICE, "es")
    assert len(payload["correct_indices"]) >= 2


def test_generated_question_accepts_correct_indexes_alias():
    question = GeneratedQuestion.model_validate(
        {
            "prompt": "Elige las correctas",
            "kind": "multiple_choice",
            "options": ["A", "B", "C", "D"],
            "correct_indexes": [0, 2],
        }
    )
    assert question.correct_indices == [0, 2]
    assert question.correct_index == 0


def test_coerce_true_false_forces_two_options():
    question = GeneratedQuestion.model_validate(
        {
            "prompt": "Una afirmación",
            "options": ["Sí", "No", "Tal vez", "Nunca"],
            "correct_index": 1,
        }
    )
    coerced = coerce_question_kind(question, QuestionKind.TRUE_FALSE, "es")
    assert coerced.kind is QuestionKind.TRUE_FALSE
    assert coerced.options == ["Verdadero", "Falso"]
    assert coerced.correct_indices == [1]


def test_coerce_multiple_choice_falls_back_when_only_one_correct():
    question = GeneratedQuestion.model_validate(
        {
            "prompt": "Una sola",
            "options": ["A", "B", "C", "D"],
            "correct_index": 2,
        }
    )
    coerced = coerce_question_kind(question, QuestionKind.MULTIPLE_CHOICE, "es")
    assert coerced.kind is QuestionKind.SINGLE_CHOICE
    assert coerced.correct_indices == [2]


@pytest.mark.asyncio
async def test_heuristic_client_honors_type_in_prompt():
    client = HeuristicClient()
    data = await client.complete_json(
        "Eres un evaluador técnico.",
        "Idioma: es. Tipo: true_false. Genera exactamente 1 preguntas.\n\nFragmento:\n"
        + " ".join(SENTENCES),
    )
    question = GeneratedQuestion.model_validate(data["questions"][0])
    assert question.kind is QuestionKind.TRUE_FALSE
    assert question.options == ["Verdadero", "Falso"]

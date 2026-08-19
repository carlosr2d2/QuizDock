from types import SimpleNamespace
from uuid import uuid4

from app.models.exam import QuestionKind, str_enum
from app.schemas.content import AttemptSubmit, QuestionPublic, QuestionResult
from app.services.generation import answer_indices, question_correct_indices, question_kind


def test_str_enum_persists_values_and_reads_legacy_names():
    column = str_enum(QuestionKind, "question_kind")
    assert column.process_bind_param(QuestionKind.SINGLE_CHOICE, None) == "single_choice"
    assert column.process_bind_param("SINGLE_CHOICE", None) == "single_choice"
    assert column.process_bind_param("TRUE_FALSE", None) == "true_false"
    assert column.process_result_value("SINGLE_CHOICE", None) is QuestionKind.SINGLE_CHOICE
    assert column.process_result_value("single_choice", None) is QuestionKind.SINGLE_CHOICE
    assert column.process_result_value("TRUE_FALSE", None) is QuestionKind.TRUE_FALSE
    assert column.process_result_value("multiple_choice", None) is QuestionKind.MULTIPLE_CHOICE


def test_question_kind_parse_accepts_legacy_names_and_values():
    assert QuestionKind.parse("single_choice") is QuestionKind.SINGLE_CHOICE
    assert QuestionKind.parse("SINGLE_CHOICE") is QuestionKind.SINGLE_CHOICE
    assert QuestionKind.parse("true_false") is QuestionKind.TRUE_FALSE
    assert QuestionKind.parse("TRUE_FALSE") is QuestionKind.TRUE_FALSE
    assert QuestionKind.parse("multiple_choice") is QuestionKind.MULTIPLE_CHOICE
    assert QuestionKind.parse("MULTIPLE_CHOICE") is QuestionKind.MULTIPLE_CHOICE
    assert QuestionKind.parse(QuestionKind.TRUE_FALSE) is QuestionKind.TRUE_FALSE


def test_question_public_loads_legacy_exam_rows():
    question_id = uuid4()
    payload = SimpleNamespace(
        id=question_id,
        prompt="¿Cuál afirmación es correcta?",
        kind="SINGLE_CHOICE",
        options=["A", "B", "C", "D"],
        difficulty="medium",
        position=0,
    )
    public = QuestionPublic.model_validate(payload)
    assert public.kind is QuestionKind.SINGLE_CHOICE
    assert public.id == question_id


def test_question_public_loads_value_style_rows():
    public = QuestionPublic.model_validate(
        {
            "id": uuid4(),
            "prompt": "El agua hierve a 100 °C.",
            "kind": "true_false",
            "options": ["Verdadero", "Falso"],
            "difficulty": "easy",
            "position": 1,
        }
    )
    assert public.kind is QuestionKind.TRUE_FALSE


def test_mixed_question_kinds_in_one_exam_payload():
    rows = [
        ("SINGLE_CHOICE", QuestionKind.SINGLE_CHOICE),
        ("true_false", QuestionKind.TRUE_FALSE),
        ("MULTIPLE_CHOICE", QuestionKind.MULTIPLE_CHOICE),
    ]
    questions = [
        QuestionPublic.model_validate(
            {
                "id": uuid4(),
                "prompt": "Pregunta",
                "kind": raw,
                "options": ["Verdadero", "Falso"] if kind is QuestionKind.TRUE_FALSE else ["A", "B", "C", "D"],
                "difficulty": "medium",
                "position": index,
            }
        )
        for index, (raw, kind) in enumerate(rows)
    ]
    assert [item.kind for item in questions] == [kind for _, kind in rows]


def test_answer_indices_normalizes_legacy_and_multi_select():
    assert answer_indices(None) == []
    assert answer_indices(2) == [2]
    assert answer_indices([2, 0, 2]) == [0, 2]
    assert answer_indices("1") == [1]


def test_question_correct_indices_falls_back_to_single_index():
    stored = SimpleNamespace(correct_indices=[1, 3], correct_index=0)
    assert question_correct_indices(stored) == [1, 3]
    legacy = SimpleNamespace(correct_indices=[], correct_index=2)
    assert question_correct_indices(legacy) == [2]


def test_question_kind_helper_reads_sqlalchemy_name_or_value():
    assert question_kind(SimpleNamespace(kind="TRUE_FALSE")) is QuestionKind.TRUE_FALSE
    assert question_kind(SimpleNamespace(kind="true_false")) is QuestionKind.TRUE_FALSE
    assert question_kind(SimpleNamespace(kind=QuestionKind.MULTIPLE_CHOICE)) is QuestionKind.MULTIPLE_CHOICE


def test_attempt_submit_accepts_single_and_multi_answers():
    payload = AttemptSubmit(answers={"a": 1, "b": [0, 2]})
    assert payload.answers["a"] == 1
    assert payload.answers["b"] == [0, 2]


def test_question_result_marks_multi_select():
    result = QuestionResult(
        question_id=uuid4(),
        prompt="Marca todas",
        kind=QuestionKind.MULTIPLE_CHOICE,
        options=["A", "B", "C", "D"],
        selected_indices=[0, 2],
        selected_index=0,
        correct_index=0,
        correct_indices=[0, 2],
        explanation=None,
        is_correct=True,
    )
    assert result.kind is QuestionKind.MULTIPLE_CHOICE
    assert result.selected_indices == [0, 2]

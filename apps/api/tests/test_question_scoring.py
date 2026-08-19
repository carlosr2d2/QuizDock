from types import SimpleNamespace

from app.models.exam import QuestionKind
from app.services.generation import answer_indices, question_correct_indices


def _score(question: SimpleNamespace, raw_answer: object) -> bool:
    return answer_indices(raw_answer) == question_correct_indices(question)


def test_true_false_requires_exact_index():
    question = SimpleNamespace(kind=QuestionKind.TRUE_FALSE, correct_index=1, correct_indices=[1])
    assert _score(question, 1) is True
    assert _score(question, 0) is False
    assert _score(question, None) is False


def test_single_choice_matches_one_index():
    question = SimpleNamespace(kind=QuestionKind.SINGLE_CHOICE, correct_index=2, correct_indices=[2])
    assert _score(question, 2) is True
    assert _score(question, [2]) is True
    assert _score(question, 1) is False


def test_multiple_choice_requires_the_full_set():
    question = SimpleNamespace(
        kind=QuestionKind.MULTIPLE_CHOICE,
        correct_index=0,
        correct_indices=[0, 2],
    )
    assert _score(question, [2, 0]) is True
    assert _score(question, [0]) is False
    assert _score(question, [0, 1, 2]) is False
    assert _score(question, 0) is False

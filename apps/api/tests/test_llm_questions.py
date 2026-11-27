from types import SimpleNamespace

import pytest

from app.models.exam import QuestionKind
from app.services.exam_quality import is_exam_worthy, polish_exam_text, usable_concept, unnatural_question
from app.services.llm import (
    GeneratedQuestion,
    HeuristicClient,
    coerce_question_kind,
    get_llm_client,
    repair_clipped_prompt,
    _concept_from,
    _heuristic_question,
    _prompt_from,
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
    assert payload is not None
    question = GeneratedQuestion.model_validate(payload)
    assert question.kind is expected
    assert question.correct_indices
    assert all(0 <= index < len(question.options) for index in question.correct_indices)


def test_heuristic_true_false_uses_spanish_labels():
    payload = _heuristic_question(SENTENCES, 0, QuestionKind.TRUE_FALSE, "es")
    assert payload is not None
    assert payload["options"] == ["Verdadero", "Falso"]
    assert "________" not in payload["prompt"]


def test_heuristic_multiple_choice_has_several_correct_answers():
    payload = _heuristic_question(SENTENCES, 0, QuestionKind.MULTIPLE_CHOICE, "es")
    assert payload is not None
    assert len(payload["correct_indices"]) >= 2
    assert "material" not in payload["prompt"].lower()
    assert "________" not in payload["prompt"]


def test_heuristic_choice_prompt_does_not_clip_source_sentence():
    source = (
        "Edición T también el menú de nombre «Edición» ofrece operaciones habituales en otros programas."
    )
    payload = _heuristic_question([source, *SENTENCES[1:]], 0, QuestionKind.SINGLE_CHOICE, "es")
    assert payload is not None
    prompt = payload["prompt"]
    clipped = source[:90].rstrip(" .")
    assert clipped not in prompt
    assert "programas" in prompt or "programas" in payload["options"][0]
    assert "¿" in prompt and prompt.endswith("?")
    assert "término completa" not in prompt.lower()
    assert "________" not in prompt
    assert "Edición" in prompt or "Edición" in payload["options"][0]


def test_heuristic_choice_prompts_vary_by_source():
    first = _heuristic_question(SENTENCES, 0, QuestionKind.SINGLE_CHOICE, "es")
    second = _heuristic_question(SENTENCES, 1, QuestionKind.SINGLE_CHOICE, "es")
    assert first is not None and second is not None
    assert first["prompt"] != second["prompt"]
    assert "inteligencia" in (first["prompt"] + first["options"][0]).lower()
    assert "procesamiento" in (second["prompt"] + second["options"][0]).lower() or "asíncrono" in (
        second["prompt"] + second["options"][0]
    ).lower()
    assert "¿" in first["prompt"] and "¿" in second["prompt"]
    assert "término completa" not in first["prompt"].lower()


def test_concept_prefers_named_term():
    assert _concept_from("Playground AI es una alternativa libre para generar imágenes.") == "Playground AI"
    assert "espacio latente" in _concept_from(
        "regularizando el espacio latente para que sea continuo."
    ).lower()


def test_teacher_prompt_is_a_short_question():
    prompt = _prompt_from("El discriminador de una GAN distingue muestras reales de generadas.", "es", 0)
    assert "¿" in prompt
    assert prompt.endswith("?")
    assert "según el documento" not in prompt.lower()
    assert "término completa" not in prompt.lower()
    assert "________" not in prompt
    assert "distingue" in prompt.lower() or "discriminador" in prompt.lower() or "GAN" in prompt


def test_usable_concept_rejects_fragments():
    assert usable_concept("Playground AI")
    assert usable_concept("el espacio latente")
    assert not usable_concept("a cómo")
    assert not usable_concept("la nube para")
    assert not usable_concept("una nueva descripción")
    assert not usable_concept("la investigación realizada")


def test_unnatural_question_flags_generic_stems():
    question = GeneratedQuestion.model_validate(
        {
            "prompt": "Según el documento, ¿cuál de las siguientes afirmaciones es correcta?",
            "options": ["A", "B", "C", "D"],
            "correct_index": 0,
        }
    )
    assert unnatural_question(question)
    natural = GeneratedQuestion.model_validate(
        {
            "prompt": "¿Qué papel cumple el discriminador en una GAN?",
            "options": ["Distinguir muestras reales", "Generar ruido", "Recortar el PDF", "Indexar páginas"],
            "correct_index": 0,
        }
    )
    assert not unnatural_question(natural)
    assert unnatural_question(
        GeneratedQuestion.model_validate(
            {
                "prompt": "¿Cuál es el propósito de la investigación realizada?",
                "options": ["A", "B", "C", "D"],
                "correct_index": 0,
            }
        )
    )
    assert unnatural_question(
        GeneratedQuestion.model_validate(
            {
                "prompt": "¿Qué es a cómo?",
                "options": ["A", "B", "C", "D"],
                "correct_index": 0,
            }
        )
    )
    assert unnatural_question(
        GeneratedQuestion.model_validate(
            {
                "prompt": "¿Qué caracteriza a la nube para?",
                "options": ["A", "B", "C", "D"],
                "correct_index": 0,
            }
        )
    )
    assert unnatural_question(
        GeneratedQuestion.model_validate(
            {
                "prompt": "¿Qué término completa esta idea del material?\n«________.»",
                "options": ["Verdadero", "Falso"],
                "correct_index": 0,
                "kind": QuestionKind.TRUE_FALSE,
            }
        )
    )


def test_repair_clipped_prompt_restores_truncated_stem():
    source = (
        "Edición T también el menú de nombre «Edición» ofrece operaciones habituales en otros programas."
    )
    prompt = f"¿Cuál afirmación es correcta en relación con {source[:90].rstrip(' .')}?"
    repaired = repair_clipped_prompt(prompt, [source, "Copiar", "Cortar", "Pegar"])
    assert repaired != prompt
    assert "________" not in repaired
    assert "término completa" not in repaired.lower()
    assert "programas" in repaired
    assert "cuál afirmación es correcta en relación con" not in repaired.lower()


def test_repair_generic_prompt_uses_option_topic():
    source = "Playground AI es una alternativa libre para generar imágenes."
    repaired = repair_clipped_prompt(
        "Según el documento, ¿cuál de las siguientes afirmaciones es correcta?",
        [source, "Otra herramienta distinta.", "Un tercer enfoque.", "Un cuarto enfoque."],
    )
    assert "alternativa" in repaired.lower() or "Playground" in repaired
    assert "término completa" not in repaired.lower()
    assert "cuál de las siguientes afirmaciones es correcta" not in repaired.lower()


def test_present_rebuilds_nonsensical_stems():
    from app.services.llm import present_exam_item

    prompt, _options = present_exam_item(
        "¿Qué es a cómo?",
        [
            "Playground AI es una alternativa libre para generar imágenes.",
            "Otra idea distinta del mismo capítulo.",
        ],
    )
    assert "a cómo" not in prompt.lower()
    assert "________" not in prompt
    assert "término completa" not in prompt.lower()
    assert "alternativa" in prompt.lower() or "Playground" in prompt


def test_present_does_not_turn_true_false_into_cloze():
    from app.services.llm import present_exam_item

    prompt, options = present_exam_item(
        "Detached permite ejecutar un contenedor en segundo plano.",
        ["Verdadero", "Falso"],
    )
    assert prompt == "Detached permite ejecutar un contenedor en segundo plano."
    assert options == ["Verdadero", "Falso"]
    assert "________" not in prompt


def test_exam_worthy_rejects_pdf_headers_and_code():
    assert not is_exam_worthy(
        "© Editorial UOC DevOps y seguridad cloud 24 o almacenamiento, nos permiten un ahorro."
    )
    assert not is_exam_worthy(
        "Herramientas de automatización._203 #Formato exec parametizado ENTRYPOINT."
    )
    assert is_exam_worthy(
        "Detached o Background permite ejecutar un contenedor en segundo plano mientras está en ejecución."
    )


def test_heuristic_detached_reads_like_a_teacher_question():
    payload = _heuristic_question(
        [
            "Detached o Background permite ejecutar un contenedor en segundo plano y enviar comandos mientras está en ejecución.",
            *SENTENCES,
        ],
        0,
        QuestionKind.SINGLE_CHOICE,
        "es",
    )
    assert payload is not None
    prompt = payload["prompt"]
    assert "término completa" not in prompt.lower()
    assert "________" not in prompt
    assert "contenedor" in prompt.lower() or "segundo plano" in prompt.lower()
    assert any("Detached" in option or "Background" in option for option in payload["options"])


def test_repair_clipped_prompt_keeps_unrelated_stems():
    prompt = "¿Cuál afirmación es correcta en relación con el menú Edición?"
    assert repair_clipped_prompt(prompt, ["Cortar", "Copiar"]) == prompt


def test_polish_joins_pdf_hyphen_breaks():
    assert polish_exam_text("IAs gene- rativas y escru- tinio público") == (
        "IAs generativas y escrutinio público"
    )
    assert polish_exam_text("las bases técni - cas estaban") == "las bases técnicas estaban"
    assert polish_exam_text("IA - definición clásica").startswith("IA -")
    assert "artificial" in polish_exam_text("inteligencia arti\ufb01cial")
    assert polish_exam_text("a identi ficar") == "a identificar"


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


def test_get_llm_client_requires_api_key(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm.get_settings",
        lambda: SimpleNamespace(llm_api_key=""),
    )
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        get_llm_client()


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

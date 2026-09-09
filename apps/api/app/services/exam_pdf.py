from html import escape
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.models.exam import Question, QuestionKind

_KIND_LABEL = {
    "es": {
        QuestionKind.TRUE_FALSE: "Verdadero / Falso",
        QuestionKind.SINGLE_CHOICE: "Opción múltiple (una correcta)",
        QuestionKind.MULTIPLE_CHOICE: "Opción múltiple (varias correctas)",
    },
    "en": {
        QuestionKind.TRUE_FALSE: "True / False",
        QuestionKind.SINGLE_CHOICE: "Multiple choice (one correct)",
        QuestionKind.MULTIPLE_CHOICE: "Multiple choice (select all that apply)",
    },
}


def render_exam_pdf(*, title: str, questions: list[Question], locale: str = "es") -> bytes:
    """Build a printable exam without answers or explanations."""
    lang = "en" if locale == "en" else "es"
    labels = _KIND_LABEL[lang]
    intro = (
        "Marca tu respuesta. No incluye la clave."
        if lang == "es"
        else "Mark your answers. This copy does not include the key."
    )
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title,
        author="QuizDock",
    )
    title_style = ParagraphStyle(
        "ExamTitle",
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        spaceAfter=6,
    )
    intro_style = ParagraphStyle(
        "ExamIntro",
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor="#444444",
        spaceAfter=12,
    )
    meta_style = ParagraphStyle(
        "ExamMeta",
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=12,
        textColor="#555555",
        spaceAfter=4,
    )
    prompt_style = ParagraphStyle(
        "ExamPrompt",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        spaceBefore=8,
        spaceAfter=4,
    )
    option_style = ParagraphStyle(
        "ExamOption",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        leftIndent=14,
    )
    story = [
        Paragraph(_safe(title), title_style),
        Paragraph(_safe(intro), intro_style),
    ]
    for index, question in enumerate(questions, start=1):
        kind = QuestionKind.parse(question.kind)
        story.append(Paragraph(_safe(f"{index}. {labels.get(kind, '')}"), meta_style))
        story.append(Paragraph(_safe(question.prompt), prompt_style))
        options = question.options or []
        for opt_index, option in enumerate(options):
            marker = chr(ord("A") + opt_index) if opt_index < 26 else str(opt_index + 1)
            story.append(Paragraph(_safe(f"{marker})  {option}"), option_style))
        story.append(Spacer(1, 6))
    doc.build(story)
    return buffer.getvalue()


def _safe(value: str) -> str:
    return escape(value or "").replace("\n", "<br/>")

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.content import FlashcardGenerateRequest


def test_flashcard_generate_requires_at_least_twenty():
    with pytest.raises(ValidationError):
        FlashcardGenerateRequest(document_id=uuid4(), card_count=12)
    payload = FlashcardGenerateRequest(document_id=uuid4(), card_count=20)
    assert payload.card_count == 20


def test_flashcard_generate_defaults_to_twenty():
    payload = FlashcardGenerateRequest(document_id=uuid4())
    assert payload.card_count == 20

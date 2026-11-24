from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_audit import AiDecisionEvent
from app.models.chat import DocumentChatMessage, DocumentConversation


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_conversation(self, row: DocumentConversation) -> DocumentConversation:
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_conversation(
        self,
        conversation_id: UUID,
        organization_id: UUID,
        *,
        user_id: UUID | None = None,
    ) -> DocumentConversation | None:
        conditions = [
            DocumentConversation.id == conversation_id,
            DocumentConversation.organization_id == organization_id,
        ]
        if user_id is not None:
            conditions.append(DocumentConversation.user_id == user_id)
        result = await self.session.execute(select(DocumentConversation).where(*conditions))
        return result.scalar_one_or_none()

    async def list_conversations(
        self,
        organization_id: UUID,
        document_id: UUID,
        user_id: UUID,
    ) -> list[DocumentConversation]:
        result = await self.session.execute(
            select(DocumentConversation)
            .where(
                DocumentConversation.organization_id == organization_id,
                DocumentConversation.document_id == document_id,
                DocumentConversation.user_id == user_id,
            )
            .order_by(DocumentConversation.updated_at.desc())
        )
        return list(result.scalars().all())

    async def add_message(self, row: DocumentChatMessage) -> DocumentChatMessage:
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_messages(
        self,
        conversation_id: UUID,
        organization_id: UUID,
    ) -> list[DocumentChatMessage]:
        result = await self.session.execute(
            select(DocumentChatMessage)
            .where(
                DocumentChatMessage.conversation_id == conversation_id,
                DocumentChatMessage.organization_id == organization_id,
            )
            .order_by(DocumentChatMessage.created_at.asc())
        )
        return list(result.scalars().all())

    async def add_decision(self, row: AiDecisionEvent) -> AiDecisionEvent:
        self.session.add(row)
        await self.session.flush()
        return row

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequestContext, get_context, get_db, require_roles
from app.models import MembershipRole
from app.schemas.appeals import DocumentChunkRead
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageRead,
    ChatSessionCreate,
    ChatSessionDetail,
    ChatSessionRead,
)
from app.schemas.content import DocumentCreate, DocumentRead
from app.services.appeals import AppealService
from app.services.content import DocumentService
from app.services.document_chat import DocumentChatService
from app.services.permissions import AUTHOR_DENIED, AUTHOR_ROLES

router = APIRouter(prefix="/documents", tags=["documents"])
WRITE_ROLES = (MembershipRole.OWNER, MembershipRole.ADMIN, MembershipRole.MEMBER)


@router.get("", response_model=list[DocumentRead])
async def list_documents(
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentRead]:
    items = await DocumentService(db).list(ctx.organization_id)
    return [DocumentRead.model_validate(item) for item in items]


@router.post("", response_model=DocumentRead, status_code=202)
async def upload_document(
    ctx: RequestContext = Depends(require_roles(*AUTHOR_ROLES, detail=AUTHOR_DENIED)),
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    language: str = Form("auto"),
) -> DocumentRead:
    payload = DocumentCreate(
        filename=file.filename or "document.pdf",
        content_type=file.content_type or "application/pdf",
        language=language,
    )
    content = await file.read()
    document = await DocumentService(db).create(
        ctx.organization_id, ctx.user.id, ctx.role, payload, content
    )
    return DocumentRead.model_validate(document)


@router.api_route("/{document_id}/cover", methods=["GET", "HEAD"])
async def get_document_cover(
    document_id: UUID,
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    service = DocumentService(db)
    document = await service.get(document_id, ctx.organization_id)
    path = service.cover_path(document)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cover not found")
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=86400"},
    )


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: UUID,
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> DocumentRead:
    document = await DocumentService(db).get(document_id, ctx.organization_id)
    return DocumentRead.model_validate(document)


@router.delete("/{document_id}", status_code=204, response_class=Response)
async def delete_document(
    document_id: UUID,
    ctx: RequestContext = Depends(require_roles(*AUTHOR_ROLES, detail=AUTHOR_DENIED)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await DocumentService(db).delete(document_id, ctx.organization_id, ctx.role, actor_id=ctx.user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkRead])
async def list_document_chunks(
    document_id: UUID,
    limit: int = 100,
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentChunkRead]:
    return await AppealService(db).list_document_chunks(
        ctx.organization_id, document_id, limit=limit
    )


@router.get("/{document_id}/chat/sessions", response_model=list[ChatSessionRead])
async def list_chat_sessions(
    document_id: UUID,
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> list[ChatSessionRead]:
    return await DocumentChatService(db).list_sessions(ctx.organization_id, ctx.user.id, document_id)


@router.post("/{document_id}/chat/sessions", response_model=ChatSessionRead, status_code=201)
async def create_chat_session(
    document_id: UUID,
    payload: ChatSessionCreate,
    ctx: RequestContext = Depends(require_roles(*WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionRead:
    return await DocumentChatService(db).create_session(
        ctx.organization_id, ctx.user.id, document_id, payload
    )


@router.get("/{document_id}/chat/sessions/{session_id}", response_model=ChatSessionDetail)
async def get_chat_session(
    document_id: UUID,
    session_id: UUID,
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionDetail:
    return await DocumentChatService(db).get_session(
        ctx.organization_id, ctx.user.id, document_id, session_id
    )


@router.post(
    "/{document_id}/chat/sessions/{session_id}/messages",
    response_model=ChatMessageRead,
)
async def send_chat_message(
    document_id: UUID,
    session_id: UUID,
    payload: ChatMessageCreate,
    ctx: RequestContext = Depends(require_roles(*WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageRead:
    return await DocumentChatService(db).send_message(
        ctx.organization_id, ctx.user.id, document_id, session_id, payload
    )

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequestContext, get_context, get_db, require_roles
from app.schemas.content import DocumentCreate, DocumentRead
from app.services.content import DocumentService
from app.services.permissions import AUTHOR_DENIED, AUTHOR_ROLES

router = APIRouter(prefix="/documents", tags=["documents"])


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

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RecoveryPreview,
    RecoveryRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserRead,
    UserUpdate,
)
from app.services.auth import AuthError, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_response(result) -> AuthResponse:
    return AuthResponse(
        access_token=result.access_token,
        user=UserRead.model_validate(result.user),
        organization_id=result.organization_id,
    )


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    service = AuthService(db)
    try:
        result = await service.register(
            payload.email, payload.password, payload.full_name, payload.invite_token, payload.locale
        )
    except AuthError as extra:
        raise HTTPException(status_code=extra.status_code, detail=extra.message) from extra
    return _auth_response(result)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    service = AuthService(db)
    try:
        result = await service.login(payload.email, payload.password, payload.invite_token)
    except AuthError as extra:
        raise HTTPException(status_code=extra.status_code, detail=extra.message) from extra
    return _auth_response(result)


@router.post("/recovery", status_code=204, response_class=Response)
async def request_recovery(
    payload: RecoveryRequest, db: AsyncSession = Depends(get_db)
) -> Response:
    await AuthService(db).request_recovery(payload.email)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/recovery/{token}", response_model=RecoveryPreview)
async def recovery_preview(token: str, db: AsyncSession = Depends(get_db)) -> RecoveryPreview:
    try:
        await AuthService(db).assert_recovery_token(token)
    except AuthError as extra:
        raise HTTPException(status_code=extra.status_code, detail=extra.message) from extra
    return RecoveryPreview(valid=True)


@router.post("/recovery/{token}", response_model=AuthResponse)
async def reset_password(
    token: str, payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
) -> AuthResponse:
    service = AuthService(db)
    try:
        result = await service.reset_password(token, payload.password)
    except AuthError as extra:
        raise HTTPException(status_code=extra.status_code, detail=extra.message) from extra
    return _auth_response(result)


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        return await AuthService(db).update_profile(
            user,
            locale=payload.locale,
            full_name=payload.full_name,
            current_password=payload.current_password,
            password=payload.password,
        )
    except AuthError as extra:
        raise HTTPException(status_code=extra.status_code, detail=extra.message) from extra

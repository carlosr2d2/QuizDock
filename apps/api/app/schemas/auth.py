from typing import Annotated
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.models.identity import InvitationStatus, MembershipRole, PlanTier


def _normalize_email(value: str) -> str:
    try:
        result = validate_email(value, check_deliverability=False, globally_deliverable=False)
    except TypeError:
        result = validate_email(value, check_deliverability=False)
    except EmailNotValidError as exc:
        raise ValueError(str(exc)) from exc
    return result.normalized


AppEmail = Annotated[str, AfterValidator(_normalize_email)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    email: AppEmail
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=200)
    invite_token: str | None = None


class LoginRequest(BaseModel):
    email: AppEmail
    password: str
    invite_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OrganizationRead(ORMModel):
    id: UUID
    name: str
    slug: str
    plan: PlanTier
    is_personal: bool
    credit_balance: int


class MembershipRead(ORMModel):
    id: UUID
    organization_id: UUID
    role: MembershipRole
    organization: OrganizationRead


class UserRead(ORMModel):
    id: UUID
    email: AppEmail
    full_name: str
    locale: str
    is_active: bool
    personal_organization_id: UUID | None
    memberships: list[MembershipRead] = []


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
    organization_id: UUID

from app.models import MembershipRole
from app.services.errors import ForbiddenError

AUTHOR_ROLES = {MembershipRole.OWNER, MembershipRole.ADMIN}
ATTEMPT_ROLES = {MembershipRole.OWNER, MembershipRole.ADMIN, MembershipRole.MEMBER}

AUTHOR_DENIED = "Solo el propietario o un administrador puede subir documentos o crear evaluaciones."


def can_author_content(role: MembershipRole) -> bool:
    return role in AUTHOR_ROLES


def require_author(role: MembershipRole) -> None:
    if not can_author_content(role):
        raise ForbiddenError(AUTHOR_DENIED)

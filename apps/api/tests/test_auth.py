import pytest

from app.core.config import get_settings
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.core.text import slugify
from app.models import MembershipRole
from app.services.auth import AuthError, AuthService
from tests.fakes import FakeMembershipRepo, FakeOrgRepo, FakeSession, FakeUserRepo, make_org, make_user

settings = get_settings()


def _auth_service() -> AuthService:
    service = AuthService(FakeSession())
    service.users = FakeUserRepo()
    service.orgs = FakeOrgRepo()
    service.memberships = FakeMembershipRepo()
    return service


@pytest.fixture
def skip_invites(monkeypatch):
    async def no_claim(self, user, token=None):
        return None

    monkeypatch.setattr("app.services.team.TeamService.claim_pending", no_claim)


def test_password_hash_roundtrip():
    hashed = hash_password("demo12345")
    assert hashed != "demo12345"
    assert verify_password("demo12345", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_access_token_embeds_user_id():
    user = make_user()
    token = create_access_token(user.id)
    payload = decode_token(token)
    assert payload["sub"] == str(user.id)


def test_decode_token_rejects_garbage():
    with pytest.raises(ValueError, match="Invalid token"):
        decode_token("not-a-jwt")


def test_slugify_normalizes_names():
    assert slugify("Ana Gomez") == "ana-gomez"
    assert slugify("Hello--World") == "hello-world"
    assert slugify("   ") == "workspace"


@pytest.mark.asyncio
async def test_register_creates_personal_workspace_with_signup_bonus(skip_invites):
    service = _auth_service()
    result = await service.register("Demo@Example.com", "demo12345", "Ana Gomez")

    assert result.user.email == "demo@example.com"
    assert result.user.locale == "es"
    assert verify_password("demo12345", result.user.hashed_password)
    org = await service.orgs.get(result.organization_id)
    assert org is not None
    assert org.is_personal is True
    assert org.credit_balance == settings.signup_bonus_credits
    assert result.user.personal_organization_id == org.id
    assert service.memberships.items[0].role is MembershipRole.OWNER
    assert decode_token(result.access_token)["sub"] == str(result.user.id)
    bonus = [item for item in service.session.added if getattr(item, "reason", None) == "signup_bonus"]
    assert bonus and bonus[0].amount == settings.signup_bonus_credits


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(skip_invites):
    service = _auth_service()
    await service.users.add(make_user(email="ana@example.com"))
    with pytest.raises(AuthError) as caught:
        await service.register("ana@example.com", "demo12345", "Ana")
    assert caught.value.status_code == 409


@pytest.mark.asyncio
async def test_register_avoids_duplicate_workspace_slug(skip_invites):
    service = _auth_service()
    await service.orgs.add(make_org(slug="ana-gomez"))
    result = await service.register("ana@example.com", "demo12345", "Ana Gomez")
    org = await service.orgs.get(result.organization_id)
    assert org is not None
    assert org.slug == "ana-gomez-2"


@pytest.mark.asyncio
async def test_login_returns_personal_workspace(skip_invites):
    service = _auth_service()
    org = make_org()
    await service.orgs.add(org)
    user = make_user(password_hash=hash_password("demo12345"), personal_organization_id=org.id)
    await service.users.add(user)

    result = await service.login("demo@example.com", "demo12345")
    assert result.organization_id == org.id
    assert decode_token(result.access_token)["sub"] == str(user.id)


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(skip_invites):
    service = _auth_service()
    await service.users.add(make_user(password_hash=hash_password("demo12345")))
    with pytest.raises(AuthError) as caught:
        await service.login("demo@example.com", "nope")
    assert caught.value.status_code == 401


@pytest.mark.asyncio
async def test_login_rejects_disabled_account(skip_invites):
    service = _auth_service()
    await service.users.add(make_user(password_hash=hash_password("demo12345"), is_active=False))
    with pytest.raises(AuthError) as caught:
        await service.login("demo@example.com", "demo12345")
    assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_register_stores_en_locale(skip_invites):
    service = _auth_service()
    result = await service.register("ana@example.com", "demo12345", "Ana Gomez", None, "en")
    assert result.user.locale == "en"


@pytest.mark.asyncio
async def test_update_locale_persists_choice():
    service = _auth_service()
    user = make_user()
    user.locale = "es"
    await service.users.add(user)
    updated = await service.update_locale(user, "en")
    assert updated.locale == "en"
    assert service.session.commits == 1

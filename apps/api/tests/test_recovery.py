from datetime import timedelta

import pytest

from app.core.security import hash_password, hash_reset_token, verify_password
from app.models.identity import PasswordResetToken
from app.models.mixins import utcnow
from app.services.auth import AuthError, AuthService
from app.services.mail import MailError
from tests.fakes import (
    FakeMailer,
    FakeMembershipRepo,
    FakeOrgRepo,
    FakePasswordResetRepo,
    FakeSession,
    FakeUserRepo,
    make_org,
    make_user,
)


@pytest.fixture
def skip_invites(monkeypatch):
    async def no_claim(self, user, token=None):
        return None

    monkeypatch.setattr("app.services.team.TeamService.claim_pending", no_claim)


def _auth(mailer: FakeMailer | None = None) -> tuple[AuthService, FakeMailer]:
    resolved = mailer or FakeMailer()
    service = AuthService(FakeSession(), mailer=resolved)
    service.users = FakeUserRepo()
    service.orgs = FakeOrgRepo()
    service.memberships = FakeMembershipRepo()
    service.resets = FakePasswordResetRepo()
    return service, resolved


def _token_from_mail(message) -> str:
    return message.text.split("/recovery/")[1].split()[0]


@pytest.mark.asyncio
async def test_request_recovery_sends_email_without_storing_raw_token():
    service, mailer = _auth()
    org = make_org()
    user = make_user(password_hash=hash_password("demo12345"), personal_organization_id=org.id)
    await service.users.add(user)

    await service.request_recovery(user.email)

    assert len(mailer.sent) == 1
    message = mailer.sent[0]
    assert message.to == user.email
    assert "Restablece tu contraseña" in message.subject
    token = _token_from_mail(message)
    assert token
    stored = service.resets.items[0]
    assert stored.token_hash == hash_reset_token(token)
    assert stored.token_hash not in message.text
    assert stored.token_hash not in message.html


@pytest.mark.asyncio
async def test_request_recovery_unknown_email_is_silent():
    service, mailer = _auth()
    await service.request_recovery("nadie@example.com")
    assert mailer.sent == []
    assert service.resets.items == []


@pytest.mark.asyncio
async def test_request_recovery_disabled_account_is_silent():
    service, mailer = _auth()
    await service.users.add(make_user(is_active=False))
    await service.request_recovery("demo@example.com")
    assert mailer.sent == []
    assert service.resets.items == []


@pytest.mark.asyncio
async def test_request_recovery_invalidates_previous_token(skip_invites):
    service, mailer = _auth()
    org = make_org()
    await service.orgs.add(org)
    user = make_user(password_hash=hash_password("demo12345"), personal_organization_id=org.id)
    await service.users.add(user)
    await service.request_recovery(user.email)
    first = _token_from_mail(mailer.sent[0])
    await service.request_recovery(user.email)
    second = _token_from_mail(mailer.sent[1])

    assert first != second
    with pytest.raises(AuthError, match="caducó"):
        await service.reset_password(first, "nuevaClave1")
    result = await service.reset_password(second, "nuevaClave1")
    assert verify_password("nuevaClave1", result.user.hashed_password)


@pytest.mark.asyncio
async def test_reset_password_replaces_hash_and_logs_in(skip_invites):
    service, mailer = _auth()
    org = make_org()
    await service.orgs.add(org)
    user = make_user(password_hash=hash_password("demo12345"), personal_organization_id=org.id)
    await service.users.add(user)
    await service.request_recovery(user.email)
    token = _token_from_mail(mailer.sent[0])

    result = await service.reset_password(token, "otraClave9")

    assert result.organization_id == org.id
    assert verify_password("otraClave9", result.user.hashed_password)
    assert not verify_password("demo12345", result.user.hashed_password)
    login = await service.login(user.email, "otraClave9")
    assert login.user.id == user.id


@pytest.mark.asyncio
async def test_reset_password_is_single_use(skip_invites):
    service, mailer = _auth()
    org = make_org()
    await service.orgs.add(org)
    user = make_user(password_hash=hash_password("demo12345"), personal_organization_id=org.id)
    await service.users.add(user)
    await service.request_recovery(user.email)
    token = _token_from_mail(mailer.sent[0])
    await service.reset_password(token, "otraClave9")

    with pytest.raises(AuthError, match="caducó"):
        await service.reset_password(token, "terceraClave")


@pytest.mark.asyncio
async def test_expired_reset_token_is_rejected():
    service, _ = _auth()
    org = make_org()
    user = make_user(password_hash=hash_password("demo12345"), personal_organization_id=org.id)
    await service.users.add(user)
    raw = "expired-token-value"
    await service.resets.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(raw),
            expires_at=utcnow() - timedelta(minutes=1),
        )
    )
    with pytest.raises(AuthError, match="caducó"):
        await service.reset_password(raw, "nuevaClave1")


@pytest.mark.asyncio
async def test_unknown_reset_token_is_rejected():
    service, _ = _auth()
    with pytest.raises(AuthError, match="caducó"):
        await service.reset_password("no-existe", "nuevaClave1")


@pytest.mark.asyncio
async def test_request_recovery_succeeds_when_mailer_fails():
    mailer = FakeMailer()
    mailer.error = MailError("smtp down")
    service, _ = _auth(mailer)
    org = make_org()
    user = make_user(password_hash=hash_password("demo12345"), personal_organization_id=org.id)
    await service.users.add(user)

    await service.request_recovery(user.email)

    assert service.resets.items
    assert mailer.sent == []


def test_hash_reset_token_is_stable_and_not_reversible():
    hashed = hash_reset_token("abc")
    assert hashed == hash_reset_token("abc")
    assert hashed != "abc"
    assert len(hashed) == 64

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.models import MembershipRole
from app.services.mail import (
    MailError,
    OutboundEmail,
    SmtpMailer,
    build_invite_email,
    build_recovery_email,
    get_mailer,
    invite_accept_url,
    recovery_url,
)


def test_build_invite_email_includes_org_role_and_link():
    expires = datetime(2026, 9, 9, tzinfo=timezone.utc)
    message = build_invite_email(
        to="ana@empresa.com",
        organization_name="Acme <Corp>",
        inviter_name="Luis",
        role=MembershipRole.ADMIN,
        accept_url="http://localhost:3000/invite/abc",
        expires_at=expires,
    )
    assert message.to == "ana@empresa.com"
    assert "Acme <Corp>" in message.subject
    assert "administrador" in message.text
    assert "http://localhost:3000/invite/abc" in message.text
    assert "09/09/2026" in message.text
    assert "Acme &lt;Corp&gt;" in message.html
    assert "href=\"http://localhost:3000/invite/abc\"" in message.html


def test_invite_accept_url_strips_trailing_slash():
    assert invite_accept_url("tok", "http://localhost:3000/") == "http://localhost:3000/invite/tok"


def test_recovery_url_and_email_include_reset_link():
    assert recovery_url("abc", "http://localhost:3000/") == "http://localhost:3000/recovery/abc"
    message = build_recovery_email(
        to="demo@example.com",
        reset_url="http://localhost:3000/recovery/abc",
        expires_minutes=60,
    )
    assert message.to == "demo@example.com"
    assert "contraseña" in message.subject
    assert "http://localhost:3000/recovery/abc" in message.text
    assert "una hora" in message.text
    assert 'href="http://localhost:3000/recovery/abc"' in message.html


def test_build_invite_email_english_uses_inviter_locale():
    expires = datetime(2026, 9, 9, tzinfo=timezone.utc)
    message = build_invite_email(
        to="ana@acme.com",
        organization_name="Acme",
        inviter_name="Luis",
        role=MembershipRole.MEMBER,
        accept_url="http://localhost:3000/invite/abc",
        expires_at=expires,
        locale="en",
    )
    assert "You're invited to Acme" in message.subject
    assert "as member" in message.text
    assert "Accept invitation" in message.html
    assert 'lang="en"' in message.html
    assert "Sep 09, 2026" in message.text


def test_build_recovery_email_english():
    message = build_recovery_email(
        to="demo@example.com",
        reset_url="http://localhost:3000/recovery/abc",
        expires_minutes=60,
        locale="en",
    )
    assert "Reset your QuizDock password" == message.subject
    assert "one hour" in message.text
    assert "Choose a new password" in message.html
    assert 'lang="en"' in message.html


def test_get_mailer_logs_when_host_is_empty():
    mailer = get_mailer(Settings(smtp_host=""))
    assert mailer.configured is False


def test_smtp_mailer_sends_html_alternative():
    settings = Settings(
        smtp_host="mailpit",
        smtp_port=1025,
        smtp_from="QuizDock <noreply@local>",
        smtp_use_tls=False,
        smtp_use_ssl=False,
        smtp_username="",
        smtp_timeout_seconds=10.0,
    )
    message = OutboundEmail(
        to="ana@empresa.com",
        subject="Hola",
        text="texto",
        html="<p>html</p>",
    )
    client = MagicMock()
    with patch("app.services.mail.smtplib.SMTP", return_value=client) as smtp:
        client.__enter__.return_value = client
        SmtpMailer(settings).send(message)

    smtp.assert_called_once_with("mailpit", 1025, timeout=10.0)
    client.send_message.assert_called_once()
    payload = client.send_message.call_args.args[0]
    assert payload["To"] == "ana@empresa.com"
    assert payload["From"] == "QuizDock <noreply@local>"
    assert payload.get_content_type() == "multipart/alternative"


def test_smtp_mailer_uses_starttls_and_login():
    settings = Settings(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="user",
        smtp_password="secret",
        smtp_use_tls=True,
    )
    client = MagicMock()
    with patch("app.services.mail.smtplib.SMTP", return_value=client):
        client.__enter__.return_value = client
        SmtpMailer(settings).send(
            OutboundEmail(to="a@b.com", subject="s", text="t", html="<p>h</p>")
        )
    client.starttls.assert_called_once()
    client.login.assert_called_once_with("user", "secret")


def test_smtp_mailer_wraps_connection_errors():
    settings = Settings(smtp_host="mailpit", smtp_port=1025)
    with patch("app.services.mail.smtplib.SMTP", side_effect=OSError("refused")):
        with pytest.raises(MailError, match="refused"):
            SmtpMailer(settings).send(
                OutboundEmail(to="a@b.com", subject="s", text="t", html="<p>h</p>")
            )

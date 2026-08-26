from __future__ import annotations

import html
import logging
import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Protocol

from app.core.config import Settings, get_settings
from app.models import MembershipRole

logger = logging.getLogger(__name__)

ROLE_LABELS = {
    MembershipRole.OWNER: "propietario",
    MembershipRole.ADMIN: "administrador",
    MembershipRole.MEMBER: "miembro",
    MembershipRole.AUDITOR: "auditor",
}


class MailError(Exception):
    """SMTP or mailer failure. Callers should not fail the invite because of this."""


@dataclass(frozen=True)
class OutboundEmail:
    to: str
    subject: str
    text: str
    html: str


class Mailer(Protocol):
    configured: bool

    def send(self, message: OutboundEmail) -> None: ...


class LoggingMailer:
    """Used when SMTP_HOST is empty. The invite still succeeds; the UI falls back to copy-link."""

    configured = False

    def send(self, message: OutboundEmail) -> None:
        logger.info("Email skipped (SMTP not configured): to=%s subject=%s", message.to, message.subject)


class SmtpMailer:
    configured = True

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def send(self, message: OutboundEmail) -> None:
        payload = _as_message(message, self._settings.smtp_from)
        try:
            with self._connect() as client:
                if self._settings.smtp_use_tls and not self._settings.smtp_use_ssl:
                    client.starttls()
                if self._settings.smtp_username:
                    client.login(self._settings.smtp_username, self._settings.smtp_password)
                client.send_message(payload)
        except (OSError, smtplib.SMTPException) as exc:
            raise MailError(str(exc)) from exc

    def _connect(self) -> smtplib.SMTP:
        host = self._settings.smtp_host
        port = self._settings.smtp_port
        timeout = self._settings.smtp_timeout_seconds
        if self._settings.smtp_use_ssl:
            return smtplib.SMTP_SSL(host, port, timeout=timeout)
        return smtplib.SMTP(host, port, timeout=timeout)


def get_mailer(settings: Settings | None = None) -> Mailer:
    resolved = settings or get_settings()
    if not resolved.smtp_host.strip():
        return LoggingMailer()
    return SmtpMailer(resolved)


def invite_accept_url(token: str, public_url: str | None = None) -> str:
    base = (public_url or get_settings().app_public_url).rstrip("/")
    return f"{base}/invite/{token}"


def build_invite_email(
    *,
    to: str,
    organization_name: str,
    inviter_name: str,
    role: MembershipRole,
    accept_url: str,
    expires_at: datetime,
) -> OutboundEmail:
    role_label = ROLE_LABELS.get(role, role.value)
    expiry = _format_expiry(expires_at)
    org = organization_name.strip() or "un equipo"
    inviter = inviter_name.strip() or "Alguien"
    subject = f"Te invitaron a {org} en QuizDock"
    text = (
        f"{inviter} te invita a unirte a {org} en QuizDock como {role_label}.\n\n"
        f"Abre este enlace para aceptar:\n{accept_url}\n\n"
        "Si ya tienes cuenta, entra con este mismo correo. Si no, el enlace te lleva a registrarte.\n"
        f"La invitación caduca el {expiry}.\n"
    )
    org_html = html.escape(org)
    inviter_html = html.escape(inviter)
    url_html = html.escape(accept_url)
    body = f"""\
<!DOCTYPE html>
<html lang="es">
  <head><meta charset="utf-8" /></head>
  <body style="font-family: system-ui, sans-serif; line-height: 1.5; color: #0f172a;">
    <p>{inviter_html} te invita a unirte a <strong>{org_html}</strong> en QuizDock como {html.escape(role_label)}.</p>
    <p>
      <a href="{url_html}" style="display: inline-block; background: #2563eb; color: #fff; padding: 10px 16px; border-radius: 8px; text-decoration: none;">
        Aceptar invitación
      </a>
    </p>
    <p>Si el botón no funciona, copia este enlace:<br /><a href="{url_html}">{url_html}</a></p>
    <p>Si ya tienes cuenta, entra con este mismo correo. Si no, el enlace te lleva a registrarte.</p>
    <p style="color: #64748b; font-size: 13px;">La invitación caduca el {html.escape(expiry)}.</p>
  </body>
</html>
"""
    return OutboundEmail(to=to, subject=subject, text=text, html=body)


def _as_message(message: OutboundEmail, from_addr: str) -> EmailMessage:
    payload = EmailMessage()
    payload["Subject"] = message.subject
    payload["From"] = from_addr
    payload["To"] = message.to
    payload.set_content(message.text, charset="utf-8")
    payload.add_alternative(message.html, subtype="html", charset="utf-8")
    return payload


def _format_expiry(value: datetime) -> str:
    expires = value
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires.astimezone(timezone.utc).strftime("%d/%m/%Y")

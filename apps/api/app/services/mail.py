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
    "es": {
        MembershipRole.OWNER: "propietario",
        MembershipRole.ADMIN: "administrador",
        MembershipRole.MEMBER: "miembro",
        MembershipRole.AUDITOR: "auditor",
    },
    "en": {
        MembershipRole.OWNER: "owner",
        MembershipRole.ADMIN: "admin",
        MembershipRole.MEMBER: "member",
        MembershipRole.AUDITOR: "auditor",
    },
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


def recovery_url(token: str, public_url: str | None = None) -> str:
    base = (public_url or get_settings().app_public_url).rstrip("/")
    return f"{base}/recovery/{token}"


def _locale(value: str | None) -> str:
    return "en" if value == "en" else "es"


def build_invite_email(
    *,
    to: str,
    organization_name: str,
    inviter_name: str,
    role: MembershipRole,
    accept_url: str,
    expires_at: datetime,
    locale: str | None = None,
) -> OutboundEmail:
    lang = _locale(locale)
    labels = ROLE_LABELS[lang]
    role_label = labels.get(role, role.value)
    expiry = _format_expiry(expires_at, lang)
    if lang == "en":
        org = organization_name.strip() or "a team"
        inviter = inviter_name.strip() or "Someone"
        subject = f"You're invited to {org} on QuizDock"
        text = (
            f"{inviter} invited you to join {org} on QuizDock as {role_label}.\n\n"
            f"Open this link to accept:\n{accept_url}\n\n"
            "If you already have an account, sign in with this same email. Otherwise the link takes you to sign up.\n"
            f"The invitation expires on {expiry}.\n"
        )
        cta = "Accept invitation"
        fallback = "If the button doesn't work, copy this link:"
        account = "If you already have an account, sign in with this same email. Otherwise the link takes you to sign up."
        expires_line = f"The invitation expires on {html.escape(expiry)}."
        join_as = "to join"
    else:
        org = organization_name.strip() or "un equipo"
        inviter = inviter_name.strip() or "Alguien"
        subject = f"Te invitaron a {org} en QuizDock"
        text = (
            f"{inviter} te invita a unirte a {org} en QuizDock como {role_label}.\n\n"
            f"Abre este enlace para aceptar:\n{accept_url}\n\n"
            "Si ya tienes cuenta, entra con este mismo correo. Si no, el enlace te lleva a registrarte.\n"
            f"La invitación caduca el {expiry}.\n"
        )
        cta = "Aceptar invitación"
        fallback = "Si el botón no funciona, copia este enlace:"
        account = "Si ya tienes cuenta, entra con este mismo correo. Si no, el enlace te lleva a registrarte."
        expires_line = f"La invitación caduca el {html.escape(expiry)}."
        join_as = "te invita a unirte a"
    org_html = html.escape(org)
    inviter_html = html.escape(inviter)
    url_html = html.escape(accept_url)
    intro = (
        f"{inviter_html} invited you to join <strong>{org_html}</strong> on QuizDock as {html.escape(role_label)}."
        if lang == "en"
        else f"{inviter_html} {join_as} <strong>{org_html}</strong> en QuizDock como {html.escape(role_label)}."
    )
    body = f"""\
<!DOCTYPE html>
<html lang="{lang}">
  <head><meta charset="utf-8" /></head>
  <body style="font-family: system-ui, sans-serif; line-height: 1.5; color: #0f172a;">
    <p>{intro}</p>
    <p>
      <a href="{url_html}" style="display: inline-block; background: #2563eb; color: #fff; padding: 10px 16px; border-radius: 8px; text-decoration: none;">
        {cta}
      </a>
    </p>
    <p>{fallback}<br /><a href="{url_html}">{url_html}</a></p>
    <p>{account}</p>
    <p style="color: #64748b; font-size: 13px;">{expires_line}</p>
  </body>
</html>
"""
    return OutboundEmail(to=to, subject=subject, text=text, html=body)


def build_recovery_email(
    *,
    to: str,
    reset_url: str,
    expires_minutes: int,
    locale: str | None = None,
) -> OutboundEmail:
    lang = _locale(locale)
    url_html = html.escape(reset_url)
    if lang == "en":
        subject = "Reset your QuizDock password"
        window = "one hour" if expires_minutes == 60 else f"{expires_minutes} minutes"
        text = (
            "We received a request to reset the password for your QuizDock account.\n\n"
            f"Open this link to choose a new one:\n{reset_url}\n\n"
            f"The link expires in {window}. If you didn't request this, ignore the email.\n"
        )
        intro = "We received a request to reset the password for your QuizDock account."
        cta = "Choose a new password"
        fallback = "If the button doesn't work, copy this link:"
        expires_line = f"The link expires in {html.escape(window)}. If you didn't request this, ignore the email."
    else:
        subject = "Restablece tu contraseña de QuizDock"
        window = "una hora" if expires_minutes == 60 else f"{expires_minutes} minutos"
        text = (
            "Recibimos una solicitud para restablecer la contraseña de tu cuenta de QuizDock.\n\n"
            f"Abre este enlace para elegir una nueva:\n{reset_url}\n\n"
            f"El enlace caduca en {window}. Si no pediste este cambio, ignora el correo.\n"
        )
        intro = "Recibimos una solicitud para restablecer la contraseña de tu cuenta de QuizDock."
        cta = "Elegir nueva contraseña"
        fallback = "Si el botón no funciona, copia este enlace:"
        expires_line = f"El enlace caduca en {html.escape(window)}. Si no pediste este cambio, ignora el correo."
    body = f"""\
<!DOCTYPE html>
<html lang="{lang}">
  <head><meta charset="utf-8" /></head>
  <body style="font-family: system-ui, sans-serif; line-height: 1.5; color: #0f172a;">
    <p>{intro}</p>
    <p>
      <a href="{url_html}" style="display: inline-block; background: #2563eb; color: #fff; padding: 10px 16px; border-radius: 8px; text-decoration: none;">
        {cta}
      </a>
    </p>
    <p>{fallback}<br /><a href="{url_html}">{url_html}</a></p>
    <p style="color: #64748b; font-size: 13px;">{expires_line}</p>
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


def _format_expiry(value: datetime, locale: str = "es") -> str:
    expires = value
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    localized = expires.astimezone(timezone.utc)
    if locale == "en":
        return localized.strftime("%b %d, %Y")
    return localized.strftime("%d/%m/%Y")

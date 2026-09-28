"""Envoi facultatif du PDF par email (SMTP générique).

Sert aussi bien à imprimer à distance (HP ePrint, Epson Connect, Canon
PRINT...) qu'à recevoir le journal dans sa boîte. Les identifiants restent
dans .env ; config.yaml n'y fait référence que par ${VARIABLE}.
"""
from __future__ import annotations

import datetime as dt
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Any

from .config import setting


@dataclass(frozen=True)
class EmailSettings:
    host: str
    port: int
    username: str
    password: str
    sender: str
    printer_to: list[str] = field(default_factory=list)
    copy_to: list[str] = field(default_factory=list)
    alert_to: list[str] = field(default_factory=list)
    title: str = "Signal Matin"

    @property
    def use_ssl(self) -> bool:
        return self.port == 465


def _addresses(value: Any) -> list[str]:
    if not value:
        return []
    items = [value] if isinstance(value, str) else list(value)
    return [str(item).strip() for item in items if str(item).strip()]


def load_email_settings(config: dict) -> EmailSettings:
    section = setting(config, "email", {}) or {}
    username = str(section.get("username") or "")
    settings = EmailSettings(
        host=str(section.get("smtp_host") or "smtp.gmail.com"),
        port=int(section.get("smtp_port") or 587),
        username=username,
        password=str(section.get("password") or ""),
        sender=str(section.get("from") or username),
        printer_to=_addresses(section.get("printer_to")),
        copy_to=_addresses(section.get("copy_to")),
        alert_to=_addresses(section.get("alert_to")) or _addresses(section.get("copy_to")),
        title=str(setting(config, "paper.title", "") or "Signal Matin"),
    )
    missing = [name for name, value in (
        ("email.username", settings.username),
        ("email.password", settings.password),
        ("email.from", settings.sender),
    ) if not value]
    if missing:
        raise SystemExit(
            "Envoi email impossible, valeurs manquantes : " + ", ".join(missing)
            + ". Renseigne SMTP_USERNAME / SMTP_PASSWORD dans .env.")
    if not settings.printer_to and not settings.copy_to:
        raise SystemExit("Envoi email : aucun destinataire (email.printer_to ou email.copy_to).")
    return settings


def _message(settings: EmailSettings, to: list[str], subject: str, body: str,
             attachment: Path | None = None) -> EmailMessage:
    message = EmailMessage()
    message["From"] = settings.sender
    message["To"] = ", ".join(to)
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain="signal-matin.local")
    message.set_content(body)
    if attachment:
        message.add_attachment(
            attachment.read_bytes(), maintype="application", subtype="pdf",
            filename=attachment.name,
        )
    return message


def build_edition_messages(settings: EmailSettings, pdf_path: Path,
                           date: dt.date) -> list[EmailMessage]:
    subject = f"{settings.title} — {date.strftime('%d/%m/%Y')}"
    messages = []
    if settings.printer_to:
        # Les services d'impression par email impriment aussi le corps du
        # message : il reste vide pour n'obtenir que le journal.
        messages.append(_message(settings, settings.printer_to, subject, "", pdf_path))
    if settings.copy_to:
        body = "Bonjour,\n\nL'édition du jour est en pièce jointe.\n\n" + settings.title
        messages.append(_message(settings, settings.copy_to, subject, body, pdf_path))
    return messages


def build_alert_message(settings: EmailSettings, date: dt.date,
                        error: BaseException) -> EmailMessage:
    body = (
        f"La génération de {settings.title} du {date.isoformat()} a échoué.\n\n"
        f"{type(error).__name__}: {error}\n\n"
        "Détails : journalctl -u signal-matin.service"
    )
    return _message(settings, settings.alert_to, f"{settings.title} — échec de l'édition", body)


def send(settings: EmailSettings, messages: list[EmailMessage]) -> None:
    context = ssl.create_default_context()
    if settings.use_ssl:
        server: smtplib.SMTP = smtplib.SMTP_SSL(settings.host, settings.port,
                                                context=context, timeout=60)
    else:
        server = smtplib.SMTP(settings.host, settings.port, timeout=60)
    with server:
        if not settings.use_ssl:
            server.starttls(context=context)
        server.login(settings.username, settings.password)
        for message in messages:
            server.send_message(message)

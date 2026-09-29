"""Mails non lus via IMAP, en lecture seule (Gmail ou tout serveur IMAP).

La boîte est ouverte avec EXAMINE et les messages lus avec BODY.PEEK : rien
n'est marqué comme lu. Avec Gmail, un mot de passe d'application suffit (le
même que pour l'envoi). Le texte des mails n'est pas enregistré dans l'édition ;
il n'est transmis qu'à l'étape de rédaction si le module ai est actif.
"""
from __future__ import annotations

import datetime as dt
import email
import html
import imaplib
import re
from dataclasses import dataclass
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime

from ..models import DataSourceStatus, DataState, MailItem

DEFAULT_QUERY = "is:unread newer_than:1d category:primary"


@dataclass(frozen=True)
class MailContent:
    """Un mail et son texte, gardé en mémoire le temps de la rédaction."""
    item: MailItem
    text: str


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return value.strip()


def _sender(value: str | None) -> str:
    name, address = parseaddr(_decode(value))
    return (name or address or "Expéditeur inconnu")[:120]


def _plain_text(message: Message) -> str:
    plain, markup = "", ""
    for part in message.walk() if message.is_multipart() else [message]:
        if part.get_content_maintype() != "text" or part.get_filename():
            continue
        try:
            payload = part.get_payload(decode=True) or b""
            text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            continue
        if part.get_content_subtype() == "plain" and not plain:
            plain = text
        elif part.get_content_subtype() == "html" and not markup:
            markup = text
    if not plain and markup:
        markup = re.sub(r"(?is)<(script|style).*?</\1>", " ", markup)
        plain = html.unescape(re.sub(r"<[^>]+>", " ", markup))
    return " ".join(plain.split())


def _search(imap: imaplib.IMAP4, query: str, gmail: bool) -> list[bytes]:
    if gmail:
        status, data = imap.uid("SEARCH", "X-GM-RAW", f'"{query}"')
    else:
        since = (dt.date.today() - dt.timedelta(days=1)).strftime("%d-%b-%Y")
        status, data = imap.uid("SEARCH", "UNSEEN", "SINCE", since)
    if status != "OK" or not data or not data[0]:
        return []
    return data[0].split()


def collect_mail(config: dict, now: dt.datetime) -> tuple[list[MailContent], DataSourceStatus]:
    host = str(config.get("imap_host") or "imap.gmail.com")
    username = str(config.get("username") or "")
    password = str(config.get("password") or "")
    if not username or not password:
        return [], DataSourceStatus(name="Mails", state=DataState.UNAVAILABLE,
                                    detail="Identifiants IMAP absents (.env).")
    limit = int(config.get("limit") or 25)
    body_chars = int(config.get("body_chars") or 1500)
    gmail = "gmail" in host
    try:
        imap = imaplib.IMAP4_SSL(host, int(config.get("imap_port") or 993), timeout=30)
        try:
            imap.login(username, password)
            imap.select(str(config.get("mailbox") or "INBOX"), readonly=True)
            uids = _search(imap, str(config.get("query") or DEFAULT_QUERY), gmail)
            total = len(uids)
            mails: list[MailContent] = []
            for uid in reversed(uids[-limit:]):  # les plus récents d'abord
                status, data = imap.uid("FETCH", uid, "(BODY.PEEK[]<0.200000>)")
                raw = next((part[1] for part in data or [] if isinstance(part, tuple)), None)
                if status != "OK" or not raw:
                    continue
                message = email.message_from_bytes(raw)
                try:
                    received = parsedate_to_datetime(message.get("Date")).astimezone(now.tzinfo)
                except Exception:
                    received = None
                mails.append(MailContent(
                    item=MailItem(sender=_sender(message.get("From")),
                                  subject=_decode(message.get("Subject"))[:240] or "(sans objet)",
                                  received=received),
                    text=_plain_text(message)[:body_chars],
                ))
        finally:
            try:
                imap.logout()
            except Exception:
                pass
    except Exception as error:
        return [], DataSourceStatus(name="Mails", state=DataState.UNAVAILABLE,
                                    detail=f"IMAP indisponible : {type(error).__name__}.")
    detail = f"{total} non lu(s) dans les dernières 24 h"
    return mails, DataSourceStatus(name="Mails", state=DataState.LIVE, detail=detail,
                                   item_count=len(mails))

import datetime as dt
import json
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from signal_matin.connectors import gmail
from signal_matin.editorial import rediger_avec_claude
from signal_matin.mock_data import construire_demo
from signal_matin.models import DataState, MailDigest
from signal_matin.normalizer import normaliser_edition
from signal_matin.renderer import render_html

NOW = dt.datetime(2026, 9, 29, 6, 50, tzinfo=ZoneInfo("Europe/Paris"))
CONFIG = {"username": "moi@gmail.com", "password": "secret"}


def _raw(sender, subject, body, html=False):
    message = EmailMessage()
    message["From"], message["Subject"] = sender, subject
    message["Date"] = "Tue, 29 Sep 2026 05:12:00 +0200"
    if html:
        message.set_content(body, subtype="html")
    else:
        message.set_content(body)
    return message.as_bytes()


class FakeImap:
    instances = []

    def __init__(self, host, port, timeout):
        self.calls = []
        FakeImap.instances.append(self)

    def login(self, user, password):
        self.calls.append(("login", user))

    def select(self, mailbox, readonly):
        self.calls.append(("select", mailbox, readonly))

    def uid(self, command, *args):
        self.calls.append((command, *args))
        if command == "SEARCH":
            return "OK", [b"11 12"]
        raw = {b"11": _raw("Alice <alice@example.org>", "=?utf-8?q?R=C3=A9union?=", "Peux-tu confirmer ?"),
               b"12": _raw("news@shop.example", "Promo", "<p>Soldes&nbsp;!</p><style>x{}</style>",
                           html=True)}[args[0]]
        return "OK", [(b"header", raw), b")"]

    def logout(self):
        self.calls.append(("logout",))


def test_collect_mail_is_read_only_and_decodes(monkeypatch):
    FakeImap.instances.clear()
    monkeypatch.setattr(gmail.imaplib, "IMAP4_SSL", FakeImap)
    mails, status = gmail.collect_mail(CONFIG, NOW)
    calls = FakeImap.instances[0].calls
    assert ("select", "INBOX", True) in calls
    assert ("SEARCH", "X-GM-RAW", f'"{gmail.DEFAULT_QUERY}"') in calls
    assert all("PEEK" in call[2] for call in calls if call[0] == "FETCH")
    assert calls[-1] == ("logout",)
    assert status.state == DataState.LIVE and status.item_count == 2
    newest, oldest = mails  # les plus récents d'abord
    assert newest.item.sender == "news@shop.example" and newest.text == "Soldes !"
    assert oldest.item.sender == "Alice" and oldest.item.subject == "Réunion"
    assert oldest.text == "Peux-tu confirmer ?"
    assert oldest.item.received.hour == 5


def test_collect_mail_without_credentials_or_on_error(monkeypatch):
    _, status = gmail.collect_mail({}, NOW)
    assert status.state == DataState.UNAVAILABLE and ".env" in status.detail

    def broken(*args, **kwargs):
        raise OSError("réseau")

    monkeypatch.setattr(gmail.imaplib, "IMAP4_SSL", broken)
    mails, status = gmail.collect_mail(CONFIG, NOW)
    assert mails == [] and "OSError" in status.detail


class Client:
    def __init__(self, answer):
        self.answer, self.sent = answer, None
        from types import SimpleNamespace
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        from types import SimpleNamespace
        self.sent = json.loads(kwargs["messages"][0]["content"])
        return SimpleNamespace(stop_reason="end_turn", model="claude-opus-5-5",
                               content=[SimpleNamespace(type="text", text=json.dumps(self.answer))])


def test_claude_triages_mail(monkeypatch):
    FakeImap.instances.clear()
    monkeypatch.setattr(gmail.imaplib, "IMAP4_SSL", FakeImap)
    mails, _ = gmail.collect_mail(CONFIG, NOW)
    edition = construire_demo(dt.date(2026, 9, 29)).model_copy(
        update={"editorial": None, "mail": MailDigest(unread=2)})
    client = Client({
        "editorial": {"title": "T", "text": "Texte."}, "items": [], "tech_insight": "",
        "markets_insight": "",
        "mail": {"summary": "Une réponse à faire.",
                 "to_handle": [{"id": "m2", "action": "Confirmer la réunion."}],
                 "fyi": [{"id": "inconnu", "note": "x"}]},
    })
    updated, _ = rediger_avec_claude(edition, {}, client=client, mails=mails)
    assert [m["id"] for m in client.sent["mails"]] == ["m1", "m2"]
    assert client.sent["mails"][1]["texte"] == "Peux-tu confirmer ?"
    digest = updated.mail
    assert digest.unread == 2 and digest.summary == "Une réponse à faire."
    assert [(m.sender, m.note) for m in digest.to_handle] == [("Alice", "Confirmer la réunion.")]
    assert digest.fyi == []

    html = render_html(normaliser_edition(updated, mode="compact"))
    assert "Confirmer la réunion." in html and "2 non lus" in html


def test_mail_is_absent_when_empty():
    edition = construire_demo(dt.date(2026, 9, 29)).model_copy(update={"mail": MailDigest()})
    assert 'class="mail-block' not in render_html(normaliser_edition(edition, mode="compact"))

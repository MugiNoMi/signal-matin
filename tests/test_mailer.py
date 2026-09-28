import datetime as dt

import pytest

from signal_matin import mailer
from signal_matin.mailer import build_alert_message, build_edition_messages, load_email_settings

CONFIG = {
    "email": {
        "username": "journal@example.org",
        "password": "secret",
        "printer_to": "imprimante@hpeprint.com",
        "copy_to": ["moi@example.org"],
    }
}


def test_settings_default_to_gmail_and_alert_copy():
    settings = load_email_settings(CONFIG)
    assert (settings.host, settings.port, settings.use_ssl) == ("smtp.gmail.com", 587, False)
    assert settings.sender == "journal@example.org"
    assert settings.printer_to == ["imprimante@hpeprint.com"]
    assert settings.alert_to == ["moi@example.org"]


def test_missing_credentials_are_reported():
    with pytest.raises(SystemExit, match="email.password"):
        load_email_settings({"email": {"username": "a@b.c", "copy_to": ["a@b.c"]}})


def test_printer_message_has_pdf_and_no_printable_body(tmp_path):
    pdf = tmp_path / "2026-09-29-signal-matin.pdf"
    pdf.write_bytes(b"%PDF-1.7 test")
    printer, copy = build_edition_messages(load_email_settings(CONFIG), pdf, dt.date(2026, 9, 29))
    assert printer["To"] == "imprimante@hpeprint.com"
    assert printer["Subject"] == "Signal Matin — 29/09/2026"
    assert printer.get_body(("plain",)).get_content().strip() == ""
    attachment = next(printer.iter_attachments())
    assert attachment.get_filename() == pdf.name
    assert attachment.get_content() == b"%PDF-1.7 test"
    assert "pièce jointe" in copy.get_body(("plain",)).get_content()


def test_alert_names_the_error():
    message = build_alert_message(load_email_settings(CONFIG), dt.date(2026, 9, 29),
                                  RuntimeError("Chromium absent"))
    assert message["To"] == "moi@example.org"
    assert "RuntimeError: Chromium absent" in message.get_content()


def test_send_uses_starttls_and_login(monkeypatch):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port))
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
        def starttls(self, context):
            calls.append(("starttls",))
        def login(self, user, password):
            calls.append(("login", user))
        def send_message(self, message):
            calls.append(("send", message["To"]))

    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    settings = load_email_settings(CONFIG)
    mailer.send(settings, [build_alert_message(settings, dt.date(2026, 9, 29), ValueError("x"))])
    assert calls == [("connect", "smtp.gmail.com", 587), ("starttls",),
                     ("login", "journal@example.org"), ("send", "moi@example.org")]


def test_generate_email_sends_alert_then_reraises(monkeypatch, tmp_path):
    from signal_matin import cli

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "email:\n  username: a@b.c\n  password: x\n  copy_to: [moi@example.org]\n",
        encoding="utf-8")
    sent = []
    monkeypatch.setattr(cli, "send", lambda settings, messages: sent.extend(messages))
    monkeypatch.setattr(cli, "_produce", lambda args, config: (_ for _ in ()).throw(
        RuntimeError("panne")))
    with pytest.raises(RuntimeError, match="panne"):
        cli.main(["generate", "--demo", "--email", "--config", str(config_path)])
    assert [m["Subject"] for m in sent] == ["Signal Matin — échec de l'édition"]

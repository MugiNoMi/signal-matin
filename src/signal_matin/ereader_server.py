"""Serveur local minimal pour retirer l'édition du jour depuis une liseuse.

Le serveur n'expose que les fichiers liseuse générés par Signal Matin. Il ne
sert jamais le dépôt, ``config.yaml`` ou les fichiers de sources.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import secrets
import socket
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, quote, urlsplit


TOKEN_FILE = ".access-token"
SUPPORTED_SUFFIXES = {".epub", ".pdf"}


def parse_refresh_time(value: str) -> dt.time:
    """Valide une heure locale au format HH:MM."""
    try:
        parsed = dt.datetime.strptime(value, "%H:%M")
    except ValueError as error:
        raise ValueError("heure attendue au format HH:MM") from error
    return parsed.time()


def ensure_access_token(directory: Path) -> str:
    """Crée une fois un jeton local non versionné, puis le réutilise."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / TOKEN_FILE
    if path.exists():
        token = path.read_text(encoding="utf-8").strip()
        if len(token) >= 32:
            return token
    token = secrets.token_urlsafe(32)
    path.write_text(token, encoding="utf-8")
    return token


def _edition_date(path: Path) -> dt.date | None:
    try:
        return dt.date.fromisoformat(path.name[:10])
    except ValueError:
        return None


@dataclass(frozen=True)
class ReaderFile:
    path: Path
    date: dt.date


class ReaderLibrary:
    """Vue bornée du dossier de publication liseuse."""

    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)

    def files(self) -> list[ReaderFile]:
        items: list[ReaderFile] = []
        for path in self.directory.iterdir():
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            date = _edition_date(path)
            if date:
                items.append(ReaderFile(path=path, date=date))
        return sorted(items, key=lambda item: (item.date, item.path.name), reverse=True)

    def latest(self, suffix: str) -> ReaderFile | None:
        suffix = suffix.lower()
        return next((item for item in self.files() if item.path.suffix.lower() == suffix), None)

    def named(self, name: str) -> ReaderFile | None:
        if Path(name).name != name:
            return None
        candidate = (self.directory / name).resolve()
        if candidate.parent != self.directory or candidate.suffix.lower() not in SUPPORTED_SUFFIXES:
            return None
        date = _edition_date(candidate)
        if not candidate.is_file() or date is None:
            return None
        return ReaderFile(path=candidate, date=date)


def _date_fr(value: dt.date) -> str:
    months = (
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    )
    return f"{value.day} {months[value.month - 1]} {value.year}"


def render_library_page(library: ReaderLibrary, token: str) -> bytes:
    """Produit une page volontairement légère pour les navigateurs e-ink."""
    latest_epub = library.latest(".epub")
    latest_pdf = library.latest(".pdf")
    buttons = []
    for item, label in ((latest_epub, "Télécharger l'EPUB"), (latest_pdf, "Télécharger le PDF e-ink")):
        if item:
            href = f"/download/{quote(item.path.name)}?token={quote(token)}"
            buttons.append(f'<a class="download" href="{href}">{html.escape(label)}</a>')
    if buttons:
        latest_date = max(item.date for item in (latest_epub, latest_pdf) if item)
        content = (
            f"<p class=\"date\">Édition du {_date_fr(latest_date)}</p>"
            f"{''.join(buttons)}"
        )
    else:
        content = "<p>Aucune édition n'est encore disponible. Actualisez dans quelques minutes.</p>"
    body = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Signal Matin</title><style>
body{{max-width:36rem;margin:10vh auto;padding:0 1.4rem;color:#111;background:#fff;
font-family:Georgia,serif;line-height:1.55}}h1{{font-size:2.4rem;line-height:1;margin:0}}
.tag{{font:700 .72rem Arial,sans-serif;letter-spacing:.12em;text-transform:uppercase}}
.date{{border-top:2px solid #111;border-bottom:1px solid #111;padding:.7rem 0}}
.download{{display:block;margin:1rem 0;padding:1rem;border:2px solid #111;color:#111;
font:bold 1rem Arial,sans-serif;text-align:center;text-decoration:none}}
small{{display:block;margin-top:2rem}}
</style></head><body><p class="tag">Le journal anti-scroll</p><h1>Signal Matin</h1>
{content}<small>Page locale — disponible uniquement depuis le réseau de la maison.</small>
</body></html>"""
    return body.encode("utf-8")


def make_handler(library: ReaderLibrary, token: str) -> type[BaseHTTPRequestHandler]:
    class ReaderHandler(BaseHTTPRequestHandler):
        server_version = "SignalMatinReader/1.0"

        def log_message(self, _format: str, *_args: object) -> None:
            # Ne jamais écrire le jeton présent dans l'URL dans un journal.
            return

        def _authorized(self, query: dict[str, list[str]]) -> bool:
            supplied = (query.get("token") or [""])[0]
            return secrets.compare_digest(supplied, token)

        def _send(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - API BaseHTTPRequestHandler
            request = urlsplit(self.path)
            if request.path == "/health":
                body = json.dumps({"ok": True}).encode("utf-8")
                self._send(HTTPStatus.OK, "application/json; charset=utf-8", body)
                return
            query = parse_qs(request.query)
            if not self._authorized(query):
                self._send(
                    HTTPStatus.UNAUTHORIZED,
                    "text/plain; charset=utf-8",
                    "Lien invalide ou expiré.".encode("utf-8"),
                )
                return
            if request.path == "/":
                self._send(
                    HTTPStatus.OK,
                    "text/html; charset=utf-8",
                    render_library_page(library, token),
                )
                return
            prefix = "/download/"
            if request.path.startswith(prefix):
                from urllib.parse import unquote

                item = library.named(unquote(request.path[len(prefix):]))
                if item is None:
                    self._send(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"Introuvable")
                    return
                body = item.path.read_bytes()
                content_type = (
                    "application/epub+zip" if item.path.suffix.lower() == ".epub"
                    else "application/pdf"
                )
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Disposition", f'attachment; filename="{item.path.name}"')
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(body)
                return
            self._send(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"Introuvable")

    return ReaderHandler


class DailyPublisher:
    """Génère au plus une fois par jour après l'heure choisie, plus au démarrage si absent."""

    def __init__(
        self,
        library: ReaderLibrary,
        generate: Callable[[dt.date], None],
        refresh_at: dt.time,
        *,
        poll_seconds: float = 30.0,
    ):
        self.library = library
        self.generate = generate
        self.refresh_at = refresh_at
        self.poll_seconds = poll_seconds
        self.last_scheduled_refresh: dt.date | None = None
        self.last_error: str = ""
        self._stop = threading.Event()

    def _has_today(self, today: dt.date) -> bool:
        return any(item.date == today and item.path.suffix.lower() == ".epub" for item in self.library.files())

    def tick(self, now: dt.datetime | None = None) -> bool:
        now = now or dt.datetime.now().astimezone()
        today = now.date()
        due = now.timetz().replace(tzinfo=None) >= self.refresh_at
        should_generate = not self._has_today(today) or (
            due and self.last_scheduled_refresh != today
        )
        if not should_generate:
            return False
        try:
            self.generate(today)
            self.last_error = ""
            if due:
                self.last_scheduled_refresh = today
            return True
        except Exception as error:  # le serveur doit conserver l'édition précédente
            self.last_error = str(error)
            return False

    def run(self) -> None:
        self.tick()
        while not self._stop.wait(self.poll_seconds):
            self.tick()

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self.run, name="signal-matin-publisher", daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        self._stop.set()


def local_ipv4_addresses() -> list[str]:
    addresses: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if not address.startswith("127.") and not address.startswith("169.254."):
                addresses.add(address)
    except OSError:
        pass
    return sorted(addresses)


def reader_urls(host: str, port: int, token: str) -> list[str]:
    hosts = local_ipv4_addresses() if host in {"0.0.0.0", "::"} else [host]
    if not hosts:
        hosts = ["127.0.0.1"]
    encoded = quote(token)
    return [f"http://{address}:{port}/?token={encoded}" for address in hosts]


def serve_reader(
    library: ReaderLibrary,
    *,
    host: str,
    port: int,
    token: str,
) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(library, token))
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


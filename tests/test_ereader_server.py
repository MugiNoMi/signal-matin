import datetime as dt
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from signal_matin.ereader_server import (
    DailyPublisher,
    ReaderLibrary,
    ensure_access_token,
    make_handler,
    parse_refresh_time,
    render_library_page,
)


def test_access_token_is_created_once_and_not_served(tmp_path):
    first = ensure_access_token(tmp_path)
    second = ensure_access_token(tmp_path)
    assert first == second
    assert len(first) >= 32
    assert all(item.path.name != ".access-token" for item in ReaderLibrary(tmp_path).files())


def test_library_page_links_only_generated_reader_files(tmp_path):
    epub = tmp_path / "2026-09-28-signal-matin.epub"
    epub.write_bytes(b"epub-content")
    (tmp_path / "config.yaml").write_text("secret: true", encoding="utf-8")
    page = render_library_page(ReaderLibrary(tmp_path), "private-token").decode("utf-8")
    assert "Télécharger" in page
    assert "EPUB" in page
    assert "2026-09-28-signal-matin.epub" in page
    assert "config.yaml" not in page


def test_http_server_requires_token_and_downloads_epub(tmp_path):
    epub = tmp_path / "2026-09-28-signal-matin.epub"
    epub.write_bytes(b"epub-content")
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), make_handler(ReaderLibrary(tmp_path), "private-token"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with pytest.raises(HTTPError) as error:
            urlopen(base + "/", timeout=2)
        assert error.value.code == 401
        with urlopen(base + "/?token=private-token", timeout=2) as response:
            assert response.status == 200
            assert "Signal Matin" in response.read().decode("utf-8")
        with urlopen(
            base + "/download/2026-09-28-signal-matin.epub?token=private-token",
            timeout=2,
        ) as response:
            assert response.headers.get_content_type() == "application/epub+zip"
            assert response.read() == b"epub-content"
    finally:
        server.shutdown()
        server.server_close()


def test_daily_publisher_refreshes_missing_then_at_scheduled_time(tmp_path):
    library = ReaderLibrary(tmp_path)
    generated = []

    def generate(date):
        generated.append(date)
        (tmp_path / f"{date.isoformat()}-signal-matin.epub").write_bytes(b"epub")

    publisher = DailyPublisher(library, generate, dt.time(8, 0))
    before = dt.datetime(2026, 9, 28, 7, 0)
    after = dt.datetime(2026, 9, 28, 8, 1)
    assert publisher.tick(before) is True
    assert publisher.tick(before) is False
    assert publisher.tick(after) is True
    assert publisher.tick(after) is False
    assert generated == [dt.date(2026, 9, 28), dt.date(2026, 9, 28)]


def test_refresh_time_validation():
    assert parse_refresh_time("08:05") == dt.time(8, 5)
    with pytest.raises(ValueError):
        parse_refresh_time("25:00")

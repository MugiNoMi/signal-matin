import datetime as dt

from signal_matin.connectors.rss import collect_rss
from signal_matin.models import DataState


RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Une information de test</title><link>https://example.org/a</link>
<description>Un resume entierement fictif pour le test du connecteur.</description>
<pubDate>Sat, 26 Sep 2026 06:00:00 +0000</pubDate></item>
</channel></rss>"""


def test_rss_is_normalized(monkeypatch):
    monkeypatch.setattr("signal_matin.connectors.rss._payload", lambda _url: RSS)
    now = dt.datetime(2026, 9, 26, 8, tzinfo=dt.timezone.utc)
    items, status = collect_rss([
        {"name": "Source test", "category": "Monde", "url": "https://example.org/rss"}
    ], now)
    assert status.state == DataState.LIVE
    assert items[0].title == "Une information de test"
    assert items[0].source.name == "Source test"


def test_empty_rss_is_optional():
    items, status = collect_rss([], dt.datetime.now().astimezone())
    assert items == []
    assert status.state == DataState.DISABLED


def test_ics_expands_recurring_events(tmp_path):
    import datetime as dt
    from zoneinfo import ZoneInfo

    from signal_matin.connectors.calendar_ics import collect_ics

    (tmp_path / "agenda.ics").write_text(
        "BEGIN:VCALENDAR\nVERSION:2.0\n"
        "BEGIN:VEVENT\nUID:1\nDTSTART;TZID=Europe/Paris:20260901T090000\n"
        "DTEND;TZID=Europe/Paris:20260901T093000\nRRULE:FREQ=WEEKLY;BYDAY=TU\n"
        "SUMMARY:Point hebdo\nEND:VEVENT\n"
        "BEGIN:VEVENT\nUID:2\nDTSTART;TZID=Europe/Paris:20260930T100000\n"
        "SUMMARY:Demain\nEND:VEVENT\nEND:VCALENDAR\n", encoding="utf-8")
    now = dt.datetime(2026, 9, 29, 6, 50, tzinfo=ZoneInfo("Europe/Paris"))
    items, status = collect_ics(["agenda.ics"], now, tmp_path)
    assert [(item.title, item.start.hour) for item in items] == [("Point hebdo", 9)]

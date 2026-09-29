import datetime as dt
from zoneinfo import ZoneInfo

from signal_matin.connectors import markets
from signal_matin.mock_data import construire_demo
from signal_matin.models import DataState, MarketsPage
from signal_matin.normalizer import normaliser_edition
from signal_matin.renderer import render_html

PARIS = ZoneInfo("Europe/Paris")
NOW = dt.datetime(2026, 9, 29, 6, 50, tzinfo=PARIS)


def _stamp(day: int, hour: int, tz: str) -> int:
    return int(dt.datetime(2026, 9, day, hour, tzinfo=ZoneInfo(tz)).timestamp())


def chart(closes, previous_close=100.0, price=None, tz="Europe/Paris"):
    """Clôtures des 25 au 29/09 ; la dernière est la séance du jour, pas encore finie."""
    days = [25, 26, 27, 28, 29][-len(closes):]
    return {"chart": {"result": [{
        "meta": {"regularMarketPrice": price or closes[-1], "chartPreviousClose": previous_close,
                 "exchangeTimezoneName": tz},
        "timestamp": [_stamp(day, 9, tz) for day in days],
        "indicators": {"quote": [{"close": closes}]},
    }]}}


def screener(*quotes):
    return {"finance": {"result": [{"quotes": [
        {"symbol": s, "shortName": n, "regularMarketPrice": 10, "regularMarketChangePercent": c}
        for s, n, c in quotes]}]}}


def fake_json(url):
    if "scrIds=day_gainers" in url:
        return screener(("KOD", "Kodiak", 177.96), ("MAAS", "Maase", 16.8))
    if "scrIds=day_losers" in url:
        return screener(("MDB", "MongoDB", -18.46))
    if url == markets.CALENDAR:
        return [
            {"title": "CPI m/m", "country": "USD", "date": "2026-09-29T08:30:00-04:00",
             "impact": "High", "forecast": "0.3%", "previous": "0.2%"},
            {"title": "JOLTS Job Openings", "country": "USD", "date": "2026-09-29T10:00:00-04:00",
             "impact": "Medium", "forecast": "7.23M", "previous": "7.27M"},
            {"title": "Bank Holiday", "country": "JPY", "date": "2026-09-29T00:00:00-04:00",
             "impact": "High"},
            {"title": "CPI m/m", "country": "USD", "date": "2026-09-30T08:30:00-04:00",
             "impact": "High"},
        ]
    symbol = url.split("/chart/")[1].split("?")[0]
    if "interval=1h" in url:  # crypto : 25 points horaires, le premier il y a 24 h
        return chart([80.0] + [90.0] * 24, tz="UTC")
    if symbol == "%5EFCHI":
        # 28/09 : 101 -> 102 (+0,99 %) ; la « séance » du 29 déjà créée doit être ignorée.
        return chart([100.0, 101.0, 102.0, 102.1], previous_close=110.0)
    if symbol == "BTC-USD":
        return chart([85.0, 88.0, 90.0], previous_close=100.0, tz="UTC")
    if symbol == "GLE.PA":
        return chart([10.0, 10.0, 11.0, 11.0])
    if symbol == "TTE.PA":
        return chart([10.0, 10.0, 9.0, 9.0])
    return chart([10.0, 10.0, 10.0, 10.0])


CONFIG = {
    "quotes": [{"symbol": "^FCHI", "name": "CAC 40"},
               {"symbol": "BTC-USD", "name": "Bitcoin", "unit": "$", "crypto": True}],
    "movers": {"count": 3, "cac40_members": {"GLE.PA": "Société Générale",
                                              "TTE.PA": "TotalEnergies", "AI.PA": "Air Liquide"}},
}


def test_collect_markets_uses_closed_sessions_movers_and_agenda(monkeypatch):
    monkeypatch.setattr(markets, "_json", fake_json)
    page, status = markets.collect_markets(CONFIG, NOW)
    assert status.state == DataState.LIVE and status.detail == "Yahoo Finance, ForexFactory"

    cac, btc = page.quotes
    assert cac.price == 102.0 and cac.change_pct == 0.99  # séance du 28, pas celle du 29
    assert cac.ytd_pct == -7.27
    assert btc.crypto and btc.change_pct == 12.5 and btc.ytd_pct == -10.0

    cac40, us = page.movers
    assert [m.name for m in cac40.gainers] == ["Société Générale"]
    assert [(m.name, m.change_pct) for m in cac40.losers] == [("TotalEnergies", -10.0)]
    assert [m.name for m in us.gainers] == ["Kodiak", "Maase"]
    assert us.losers[0].change_pct == -18.46

    assert [(e.time, e.title, e.impact) for e in page.agenda] == [
        ("14h30", "Inflation (IPC) sur un mois", "Fort"),
        ("16h00", "Offres d'emploi (JOLTS)", "Moyen"),
    ]


def test_a_failing_source_is_reported_without_hiding_the_rest(monkeypatch):
    def flaky(url):
        if "screener" in url:
            raise OSError("réseau")
        return fake_json(url)

    monkeypatch.setattr(markets, "_json", flaky)
    page, status = markets.collect_markets(CONFIG, NOW)
    assert status.state == DataState.LIVE
    assert "palmarès US" in status.detail
    assert [m.title for m in page.movers] == ["CAC 40"]


def test_everything_down_is_unavailable(monkeypatch):
    def down(url):
        raise OSError("réseau")

    monkeypatch.setattr(markets, "_json", down)
    page, status = markets.collect_markets(CONFIG, NOW)
    assert page.is_empty() and status.state == DataState.UNAVAILABLE


def test_market_strip_and_page_are_rendered():
    html = render_html(normaliser_edition(construire_demo(dt.date(2026, 9, 26)), mode="compact"))
    assert 'class="market-strip"' in html
    assert 'data-label="Marchés"' in html
    assert "80 000,00 $" in html
    assert "−1,80 %" in html


def test_no_markets_without_data():
    edition = construire_demo(dt.date(2026, 9, 26)).model_copy(update={"markets": MarketsPage()})
    html = render_html(normaliser_edition(edition, mode="compact"))
    assert 'class="market-strip"' not in html and 'data-label="Marchés"' not in html

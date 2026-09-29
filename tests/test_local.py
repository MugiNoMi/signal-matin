import datetime as dt
import json
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from signal_matin.connectors import local
from signal_matin.editorial import rediger_avec_claude
from signal_matin.mock_data import construire_demo
from signal_matin.models import DataSourceStatus, DataState, Ephemeris, EphemerisEntry, LocalPage, NewsItem, SourceRef
from signal_matin.normalizer import normaliser_edition
from signal_matin.renderer import render_html

PARIS = ZoneInfo("Europe/Paris")
FRIDAY = dt.datetime(2026, 10, 2, 6, 50, tzinfo=PARIS)


def test_moon_phases():
    assert local.moon_phase(dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)) == "Nouvelle lune"
    assert local.moon_phase(dt.datetime(2000, 1, 21, 12, tzinfo=dt.timezone.utc)) == "Pleine lune"


def fake_json(url):
    if url.startswith(local.NOMINIS):
        return {"response": {
            "saints": {"majeurs": {"Ange": {"valeur": "Saints Anges gardiens", "resume": "Fête."}}},
            "prenoms": {"majeurs": {"Ange": {}, "Léger": {}, "Ruth": {}}}}}
    if "onthisday" in url:
        return {"selected": [{"year": 1997, "text": "Traité d'Amsterdam."}],
                "births": [{"year": 2002, "text": "Inconnu."}, {"year": 1869, "text": "Gandhi."}],
                "holidays": [{"text": "Organisation des Nations unies : journée internationale "
                                      "de la non-violence depuis 2007."},
                             {"text": "Guinée : fête nationale."}]}
    if url.startswith(local.SUN):
        return {"daily": {"sunrise": ["2026-10-02T07:38"], "sunset": ["2026-10-02T19:23"],
                          "daylight_duration": [42300.0]}}
    raise AssertionError(url)


def test_collect_ephemeris(monkeypatch):
    monkeypatch.setattr(local, "_json", fake_json)
    ephemeris, status = local.collect_ephemeris({}, FRIDAY, 46.43, 4.66)
    assert status.state == DataState.LIVE and "manquant" not in status.detail
    assert (ephemeris.saint, ephemeris.names) == ("Saints Anges gardiens", ["Ange", "Léger", "Ruth"])
    assert ephemeris.world_days == ["Journée internationale de la non-violence"]
    assert (ephemeris.sunrise, ephemeris.sunset, ephemeris.daylight) == ("7h38", "19h23", "11 h 45")
    assert ephemeris.history[0].year == 1997 and len(ephemeris.births) == 2


def _item(title):
    return NewsItem(title=title, category="Local", summary="Résumé.",
                    source=SourceRef(name="Le JSL"))


def test_local_news_keeps_nearby_places_first(monkeypatch):
    items = [_item("Digoin. Incendie dans un château"), _item("Mâcon. Le collège a chaud"),
             _item("Cluny. Nouveau marché"), _item("Cluny. Nouveau marché")]
    status = DataSourceStatus(name="Actus locales", state=DataState.LIVE)
    monkeypatch.setattr(local, "collect_rss", lambda *args, **kwargs: (items, status))
    news, status = local.collect_local_news({"places": ["Cluny", "Mâcon"]}, FRIDAY)
    assert [item.title for item in news] == ["Cluny. Nouveau marché", "Mâcon. Le collège a chaud"]
    assert status.item_count == 2


PAGE = """
<a data-layer-wpet-offer-title="Octobre Rose" data-layer-wpet-offer-flux="Fêtes">
  <span>Vendredi 02 oct. 2026</span> <h3>Octobre Rose</h3> <span>IGE</span></a>
<a data-layer-wpet-offer-title="A fleur de peau" href="https://example.org/expo">
  Exposition 11 septembre 07 novembre 2026 A fleur de peau CLUNY</a>
<a data-layer-wpet-offer-title="Spectacle hors week-end">Le 09 octobre 2026 CLUNY</a>
<a data-layer-wpet-offer-title="Octobre Rose">Vendredi 02 oct. 2026 IGE</a>
"""


def test_weekend_events_are_filtered_and_one_offs_first(monkeypatch):
    monkeypatch.setattr(local, "_get", lambda url: PAGE.encode())
    events, status = local.collect_local_events({"url": "https://example.org"}, FRIDAY)
    assert [(e.title, e.place, e.category) for e in events] == [
        ("Octobre Rose", "Ige", ""), ("A fleur de peau", "Cluny", "Exposition")]
    assert events[1].end == dt.date(2026, 11, 7) and events[1].url == "https://example.org/expo"
    assert status.state == DataState.LIVE
    _, status = local.collect_local_events({"url": "x"}, FRIDAY - dt.timedelta(days=2))
    assert status.state == DataState.DISABLED


def test_claude_picks_ephemeris_and_summarises_local_news():
    edition = construire_demo(dt.date(2026, 10, 2)).model_copy(update={
        "editorial": None,
        "local": LocalPage(news=[_item("Cluny. Nouveau marché")], ephemeris=Ephemeris(
            history=[EphemerisEntry(year=1997, text="A"), EphemerisEntry(year=1935, text="B")],
            births=[EphemerisEntry(year=2002, text="C"), EphemerisEntry(year=1869, text="D")]))})
    answer = {"editorial": {"title": "T", "text": "X."}, "tech_insight": "", "markets_insight": "",
              "items": [{"id": "l1", "summary": "Le marché ouvre.", "why_it_matters": "Enjeu."}],
              "ephemeris": {"history": ["h0", "h1"], "births": ["b1"]},
              "mail": {"summary": "", "to_handle": [], "fyi": []}}
    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=lambda **k: SimpleNamespace(
        stop_reason="end_turn", model="claude-opus-5-5",
        content=[SimpleNamespace(type="text", text=json.dumps(answer))]))))
    updated, _ = rediger_avec_claude(edition, {}, client=client)
    assert updated.local.news[0].summary == "Le marché ouvre."
    assert [e.year for e in updated.local.ephemeris.history] == [1935, 1997]
    assert [e.text for e in updated.local.ephemeris.births] == ["D"]


def test_local_page_and_front_line_render():
    html = render_html(normaliser_edition(construire_demo(dt.date(2026, 10, 2)), mode="compact"))
    assert 'class="ephemeris-line"' in html and "Bonne fête aux Prénom A et Prénom B" in html
    assert "C’était un 2 octobre" in html and "Sorties du week-end" in html
    assert "Vendredi 2 octobre" in html

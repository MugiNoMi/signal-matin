import datetime as dt
from zoneinfo import ZoneInfo

from signal_matin.connectors import sport
from signal_matin.mock_data import construire_demo
from signal_matin.models import DataState, SportPage
from signal_matin.normalizer import normaliser_edition
from signal_matin.renderer import render_html

PARIS = ZoneInfo("Europe/Paris")
NOW = dt.datetime(2026, 10, 21, 6, 50, tzinfo=PARIS)


def _team(abbr, short, location, score, home, winner=False, record="10-5", leaders=()):
    return {
        "homeAway": "home" if home else "away", "score": score, "winner": winner,
        "records": [{"summary": record}],
        "team": {"abbreviation": abbr, "shortDisplayName": short, "displayName": short,
                 "location": location},
        "leaders": [{"name": name, "leaders": [{"displayValue": value,
                                                "athlete": {"displayName": player}}]}
                    for name, value, player in leaders],
    }


def _nba_game(date, state, *competitors):
    return {"date": date, "competitions": [{
        "status": {"type": {"state": state}}, "competitors": list(competitors)}]}


RESPONSES = {
    # Match des Spurs le 21/10 heure US, soit la nuit suivante à Paris.
    "basketball/nba/scoreboard?dates=20261021": {"events": [_nba_game(
        "2026-10-22T00:30Z", "pre",
        _team("SA", "Spurs", "San Antonio", "0", True),
        _team("LAL", "Lakers", "Los Angeles", "0", False))]},
    "basketball/nba/scoreboard?dates=20261020": {"events": [
        _nba_game("2026-10-21T00:00Z", "post",
                  _team("SA", "Spurs", "San Antonio", "112", False, True, "1-0",
                        [("rating", "31 PTS, 12 REB", "Victor Wembanyama"),
                         ("assists", "9", "De'Aaron Fox"), ("rebounds", "12", "Victor Wembanyama")]),
                  _team("DAL", "Mavericks", "Dallas", "104", True, False, "0-1",
                        [("rating", "27 PTS, 8 AST", "Luka Doncic")])),
        _nba_game("2026-10-21T02:00Z", "post",
                  _team("BOS", "Celtics", "Boston", "99", True, True),
                  _team("NY", "Knicks", "New York", "95", False)),
    ]},
    "basketball/nba/teams/sa": {"team": {"shortDisplayName": "Spurs",
                                          "displayName": "San Antonio Spurs",
                                          "record": {"items": [{"summary": "1-0"}]},
                                          "standingSummary": "1st in Southwest Division"}},
    "soccer/uefa.champions/scoreboard?dates=20261021": {"events": [{
        "date": "2026-10-21T19:00Z", "competitions": [{
            "status": {"type": {"state": "pre"}}, "venue": {"fullName": "Allianz Arena"},
            "competitors": [
                {"homeAway": "home", "team": {"displayName": "Bayern Munich"}},
                {"homeAway": "away", "team": {"displayName": "Arsenal"}}]}]}]},
    "soccer/uefa.champions/standings": {"children": [{"standings": {"entries": [
        {"team": {"displayName": "Arsenal"}, "stats": [
            {"name": "rank", "displayValue": "2"}, {"name": "points", "displayValue": "3"}]},
        {"team": {"displayName": "Bayern Munich"}, "stats": [
            {"name": "rank", "displayValue": "1"}, {"name": "points", "displayValue": "6"}]},
    ]}}]},
    "leagues/atp/rankings": {"items": [{"$ref": "http://sports.core.api.espn.com/r/atp"}]},
    "sports.core.api.espn.com/r/atp": {"ranks": [
        {"current": 1, "athlete": {"$ref": "http://x/athletes/3623?lang=en"}},
        {"current": 25, "athlete": {"$ref": "http://x/athletes/999?lang=en"}}]},
    "tennis/atp/scoreboard": {"events": [{"name": "Shanghai Masters", "groupings": [
        {"grouping": {"displayName": "Men's Singles"}, "competitions": [
            {"date": "2026-10-21T08:00Z", "timeValid": True, "round": {"displayName": "Round of 16"},
             "status": {"type": {"state": "post"}},
             "competitors": [
                 {"id": "3623", "winner": True, "athlete": {"displayName": "Jannik Sinner"},
                  "linescores": [{"value": 6}, {"value": 7}]},
                 {"id": "999", "winner": False, "athlete": {"displayName": "Autre Joueur"},
                  "linescores": [{"value": 4}, {"value": 5}]}]},
            {"date": "2026-10-21T10:00Z", "timeValid": True, "round": {"displayName": "Round of 16"},
             "status": {"type": {"state": "pre"}},
             "competitors": [{"id": "1", "athlete": {"displayName": "Hors top"}},
                             {"id": "2", "athlete": {"displayName": "Hors top bis"}}]},
        ]},
        {"grouping": {"displayName": "Men's Doubles"}, "competitions": []},
    ]}]},
}

CONFIG = {
    "tennis": {"tours": ["atp"], "top": 20},
    "football": {"leagues": [{"code": "uefa.champions", "name": "Ligue des champions"}]},
    "nba": {"team": "SA", "recap_all_games": True},
}


def fake_json(url):
    for key, value in RESPONSES.items():
        if url.endswith(key):
            return value
    raise AssertionError(f"URL inattendue : {url}")


def test_collect_sport_builds_today_recaps_and_tables(monkeypatch):
    monkeypatch.setattr(sport, "_json", fake_json)
    page, status = sport.collect_sport(CONFIG, NOW)
    assert status.state == DataState.LIVE and status.detail == "ESPN"

    nba = next(e for e in page.today if e.sport == "basketball")
    assert nba.highlight
    assert nba.label == "Spurs – Lakers (à domicile)"
    assert nba.when == "19h30 heure de San Antonio (jeu. 22/10 à 2h30 heure de Paris)"

    tennis = [e for e in page.today if e.sport == "tennis"]
    assert [e.label for e in tennis] == ["Jannik Sinner (1) bat Autre Joueur 6-4 7-5"]
    assert tennis[0].detail == "8e de finale"

    football = next(e for e in page.today if e.sport == "football")
    assert (football.label, football.when) == ("Bayern Munich – Arsenal", "21h00")
    assert page.tables[0].rows[0][1] == "Bayern Munich"

    spurs, other = page.recaps
    assert spurs.highlight and spurs.headline == "Spurs 112 – 104 Mavericks"
    assert spurs.lines[0] == "Victoire à l'extérieur, bilan 1-0"
    assert spurs.lines[1] == ("Spurs : Victor Wembanyama (31 pts, 12 rbds) ; De'Aaron Fox 9 pd")
    assert other.headline == "Celtics 99 – 95 Knicks"
    assert page.notes == ["Spurs : bilan 1-0, 1er de la division Sud-Ouest"]


def test_one_failing_sport_does_not_hide_the_others(monkeypatch):
    def flaky(url):
        if "tennis" in url or "rankings" in url:
            raise OSError("réseau")
        return fake_json(url)

    monkeypatch.setattr(sport, "_json", flaky)
    page, status = sport.collect_sport(CONFIG, NOW)
    assert status.state == DataState.LIVE
    assert "Tennis" in status.detail
    assert not any(e.sport == "tennis" for e in page.today)
    assert any(e.sport == "basketball" for e in page.today)


def test_nba_standings_only_on_configured_weekday(monkeypatch):
    monkeypatch.setattr(sport, "_json", fake_json)
    page, _ = sport.collect_sport({"nba": {"team": "SA"}}, NOW)  # mercredi
    assert not page.tables


def test_sport_page_and_front_box_are_rendered():
    html = render_html(normaliser_edition(construire_demo(dt.date(2026, 9, 26)), mode="standard"))
    assert 'data-label="Sport"' in html
    assert 'class="sport-front"' in html
    assert "Cette nuit" in html


def test_no_sport_page_without_sport_data():
    edition = construire_demo(dt.date(2026, 9, 26)).model_copy(update={"sport": SportPage()})
    html = render_html(normaliser_edition(edition, mode="standard"))
    assert 'data-label="Sport"' not in html
    assert 'class="front-lower"' in html

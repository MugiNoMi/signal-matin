"""Sport : tennis ATP/WTA, football et NBA via les données publiques d'ESPN.

Aucune clé n'est nécessaire. Chaque discipline est indépendante : une source
en panne n'empêche pas les autres d'apparaître dans le journal.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.request
from typing import Any
from zoneinfo import ZoneInfo

from ..models import DataSourceStatus, DataState, SportEvent, SportPage, SportRecap, SportTable

SITE = "https://site.api.espn.com/apis/site/v2/sports"
STANDINGS = "https://site.api.espn.com/apis/v2/sports"
CORE = "https://sports.core.api.espn.com/v2/sports"

_DAYS = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")
_ROUNDS = {
    "final": "Finale", "semifinal": "Demi-finale", "quarterfinal": "Quart de finale",
    "round of 16": "8e de finale", "round of 32": "16e de finale",
    "round 1": "1er tour", "round 2": "2e tour", "round 3": "3e tour", "round 4": "4e tour",
    "qualifying final": "Qualifications, dernier tour",
}
_STAT_UNITS = {"PTS": "pts", "REB": "rbds", "AST": "pd", "STL": "int", "BLK": "ctres"}
_DIVISIONS = {
    "southwest": "Sud-Ouest", "northwest": "Nord-Ouest", "pacific": "Pacifique",
    "central": "Centrale", "atlantic": "Atlantique", "southeast": "Sud-Est",
}


# Le pare-feu d'ESPN refuse certains User-Agent trop courts : on s'identifie
# clairement, avec l'adresse du projet.
_HEADERS = {
    "User-Agent": "Signal-Matin/1.0 (+https://github.com/sosoj92/signal-matin)",
    "Accept": "*/*",
}


def _json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def _parse_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _hour(value: dt.datetime) -> str:
    return f"{value.hour}h{value.minute:02d}"


def _day_hour(value: dt.datetime) -> str:
    return f"{_DAYS[value.weekday()]} {value:%d/%m} à {_hour(value)}"


def _round(name: str) -> str:
    key = name.strip().casefold()
    if key.startswith("qualifying") and key not in _ROUNDS:
        return "Qualifications"
    return _ROUNDS.get(key, name)


def _stat_line(value: str) -> str:
    """« 31 PTS, 6 AST » -> « 31 pts, 6 pd »."""
    return re.sub(r"\b(PTS|REB|AST|STL|BLK)\b", lambda m: _STAT_UNITS[m.group(1)], value)


# --- Tennis -----------------------------------------------------------------

def _tennis_ranks(tour: str, top: int) -> dict[str, int]:
    listing = _json(f"{CORE}/tennis/leagues/{tour}/rankings")
    ref = listing["items"][0]["$ref"].replace("http://", "https://", 1)
    ranks = _json(ref)["ranks"]
    result = {}
    for entry in ranks:
        position = int(entry.get("current") or 0)
        athlete_id = entry["athlete"]["$ref"].split("/athletes/")[1].split("?")[0]
        if 0 < position <= top:
            result[athlete_id] = position
    return result


def _player(competitor: dict, ranks: dict[str, int]) -> str:
    name = competitor.get("athlete", {}).get("displayName") or "À déterminer"
    rank = ranks.get(str(competitor.get("id")))
    return f"{name} ({rank})" if rank else name


def _tennis_score(winner: dict, loser: dict) -> str:
    sets = zip(winner.get("linescores") or [], loser.get("linescores") or [])
    return " ".join(f"{int(w.get('value', 0))}-{int(l.get('value', 0))}" for w, l in sets)


def _tennis(config: dict, today: dt.date, tz: ZoneInfo) -> list[SportEvent]:
    top = int(config.get("top") or 20)
    events: list[SportEvent] = []
    for tour in config.get("tours") or ["atp", "wta"]:
        ranks = _tennis_ranks(tour, top)
        board = _json(f"{SITE}/tennis/{tour}/scoreboard")
        for tournament in board.get("events", []):
            for grouping in tournament.get("groupings", []):
                if "singles" not in grouping.get("grouping", {}).get("displayName", "").casefold():
                    continue
                for match in grouping.get("competitions", []):
                    start = _parse_time(match["date"]).astimezone(tz)
                    players = match.get("competitors", [])
                    if start.date() != today or len(players) != 2:
                        continue
                    if not any(str(p.get("id")) in ranks for p in players):
                        continue
                    state = match.get("status", {}).get("type", {}).get("state", "pre")
                    winner = next((p for p in players if p.get("winner")), None)
                    if state == "post" and winner:
                        loser = players[1] if winner is players[0] else players[0]
                        label = (f"{_player(winner, ranks)} bat {_player(loser, ranks)} "
                                 f"{_tennis_score(winner, loser)}").strip()
                        when = "Terminé"
                    else:
                        label = f"{_player(players[0], ranks)} – {_player(players[1], ranks)}"
                        if state == "in":
                            when = "En cours"
                        elif match.get("timeValid", True):
                            when = _hour(start)
                        else:
                            when = "Horaire à confirmer"
                    events.append(SportEvent(
                        sport="tennis",
                        competition=f"{tour.upper()} · {tournament.get('name', 'Tournoi')}",
                        label=label, when=when,
                        detail=_round(match.get("round", {}).get("displayName", "")),
                        start=start,
                    ))
    return sorted(events, key=lambda e: (e.competition, e.start or dt.datetime.max.replace(tzinfo=tz)))


# --- Football ----------------------------------------------------------------

def _football(config: dict, today: dt.date, tz: ZoneInfo) -> tuple[list[SportEvent], list[SportTable]]:
    events: list[SportEvent] = []
    tables: list[SportTable] = []
    for league in config.get("leagues") or []:
        code = league["code"]
        name = league.get("name") or code
        board = _json(f"{SITE}/soccer/{code}/scoreboard?dates={today:%Y%m%d}")
        count = 0
        for game in board.get("events", []):
            competition = game["competitions"][0]
            start = _parse_time(game["date"]).astimezone(tz)
            if start.date() != today:
                continue
            teams = {c["homeAway"]: c for c in competition["competitors"]}
            home, away = teams.get("home"), teams.get("away")
            if not home or not away:
                continue
            state = competition.get("status", {}).get("type", {}).get("state", "pre")
            if state == "post":
                label = (f"{home['team']['displayName']} {home.get('score', '')} – "
                         f"{away.get('score', '')} {away['team']['displayName']}")
                when = "Terminé"
            else:
                label = f"{home['team']['displayName']} – {away['team']['displayName']}"
                when = "En cours" if state == "in" else _hour(start)
            events.append(SportEvent(
                sport="football", competition=name, label=label, when=when,
                detail=competition.get("venue", {}).get("fullName", ""), start=start,
            ))
            count += 1
        if count and league.get("table", "match_days") == "match_days":
            tables.append(_football_table(code, name))
    return events, tables


def _stats(entry: dict) -> dict[str, str]:
    return {s["name"]: str(s.get("displayValue", s.get("value", ""))) for s in entry.get("stats", [])}


def _football_table(code: str, name: str) -> SportTable:
    data = _json(f"{STANDINGS}/soccer/{code}/standings")
    group = (data.get("children") or [data])[0]
    rows = []
    for entry in group["standings"]["entries"]:
        s = _stats(entry)
        rows.append([s.get("rank", ""), entry["team"]["displayName"], s.get("gamesPlayed", ""),
                     s.get("wins", ""), s.get("ties", ""), s.get("losses", ""),
                     s.get("pointDifferential", ""), s.get("points", "")])
    rows.sort(key=lambda row: int(row[0]) if row[0].isdigit() else 99)
    return SportTable(title=f"{name} : classement", rows=rows,
                      columns=["Rg", "Équipe", "J", "G", "N", "P", "Diff", "Pts"])


# --- NBA ---------------------------------------------------------------------

def _team_side(competition: dict, abbreviation: str) -> tuple[dict | None, dict | None]:
    mine = other = None
    for competitor in competition.get("competitors", []):
        if competitor["team"].get("abbreviation", "").upper() == abbreviation:
            mine = competitor
        else:
            other = competitor
    return mine, other


def _leader(competitor: dict, name: str) -> tuple[str, str] | None:
    for group in competitor.get("leaders", []):
        if group.get("name") == name and group.get("leaders"):
            best = group["leaders"][0]
            return best["athlete"]["displayName"], best.get("displayValue", "")
    return None


def _performances(competitor: dict) -> str:
    team = competitor["team"].get("shortDisplayName") or competitor["team"]["displayName"]
    rating = _leader(competitor, "rating")
    others: dict[str, list[str]] = {}
    for stat, unit in (("points", "pts"), ("rebounds", "rbds"), ("assists", "pd")):
        best = _leader(competitor, stat)
        if best and (not rating or best[0] != rating[0]):
            others.setdefault(best[0], []).append(f"{best[1]} {unit}")
    parts = [f"{rating[0]} ({_stat_line(rating[1])})"] if rating else []
    parts += [f"{name} {', '.join(values)}" for name, values in others.items()]
    return f"{team} : " + " ; ".join(parts) if parts else team


def _score_headline(first: dict, second: dict) -> str:
    def name(c: dict) -> str:
        return c["team"].get("shortDisplayName") or c["team"]["displayName"]
    return f"{name(first)} {first.get('score', '')} – {second.get('score', '')} {name(second)}"


def _nba(config: dict, today: dt.date, tz: ZoneInfo) -> tuple[
        list[SportEvent], list[SportRecap], list[SportTable], list[str]]:
    team = str(config.get("team") or "SA").upper()
    team_tz = ZoneInfo(str(config.get("team_timezone") or "America/Chicago"))
    events: list[SportEvent] = []
    recaps: list[SportRecap] = []
    tables: list[SportTable] = []
    notes: list[str] = []

    # Match du jour : la date américaine du jour, souvent la nuit suivante en France.
    board = _json(f"{SITE}/basketball/nba/scoreboard?dates={today:%Y%m%d}")
    for game in board.get("events", []):
        competition = game["competitions"][0]
        mine, other = _team_side(competition, team)
        if not mine or not other:
            continue
        start = _parse_time(game["date"])
        local, paris = start.astimezone(team_tz), start.astimezone(tz)
        city = mine["team"].get("location") if mine.get("homeAway") == "home" else other["team"].get("location")
        where = "à domicile" if mine.get("homeAway") == "home" else "à l'extérieur"
        record = (mine.get("records") or [{}])[0].get("summary", "")
        events.append(SportEvent(
            sport="basketball", competition="NBA",
            label=f"{mine['team']['shortDisplayName']} – {other['team']['shortDisplayName']} ({where})",
            when=f"{_hour(local)} heure de {city or 'match'} ({_day_hour(paris)} heure de Paris)",
            detail=f"Bilan {record}" if record else "", start=paris, highlight=True,
        ))

    # Résumé de la veille (date américaine précédente).
    yesterday = _json(f"{SITE}/basketball/nba/scoreboard?dates={today - dt.timedelta(days=1):%Y%m%d}")
    for game in yesterday.get("events", []):
        competition = game["competitions"][0]
        if competition.get("status", {}).get("type", {}).get("state") != "post":
            continue
        mine, other = _team_side(competition, team)
        if mine and other:
            outcome = "Victoire" if mine.get("winner") else "Défaite"
            where = "à domicile" if mine.get("homeAway") == "home" else "à l'extérieur"
            record = (mine.get("records") or [{}])[0].get("summary", "")
            recaps.insert(0, SportRecap(
                competition="NBA", headline=_score_headline(mine, other), highlight=True,
                lines=[f"{outcome} {where}" + (f", bilan {record}" if record else ""),
                       _performances(mine), _performances(other)],
            ))
        elif config.get("recap_all_games", False):
            home, away = sorted(competition["competitors"], key=lambda c: c["homeAway"] != "home")
            recaps.append(SportRecap(
                competition="NBA", headline=_score_headline(home, away),
                lines=[_performances(home), _performances(away)],
            ))

    # Bilan et classement de la division de l'équipe suivie.
    info = _json(f"{SITE}/basketball/nba/teams/{team.lower()}").get("team", {})
    record = ((info.get("record") or {}).get("items") or [{}])[0].get("summary", "")
    standing = _standing_fr(info.get("standingSummary", ""))
    if record and record != "0-0":
        notes.append(f"{info.get('shortDisplayName', team)} : bilan {record}"
                     + (f", {standing}" if standing else ""))

    weekday = int(config.get("standings_weekday", 6))
    if today.weekday() == weekday:
        tables.extend(_nba_tables(info.get("displayName", "")))
    return events, recaps, tables, notes


def _standing_fr(value: str) -> str:
    match = re.match(r"(\d+)(?:st|nd|rd|th) in (\w+) Division", value)
    if not match:
        return ""
    rank = "1er" if match.group(1) == "1" else f"{match.group(1)}e"
    division = _DIVISIONS.get(match.group(2).casefold(), match.group(2))
    return f"{rank} de la division {division}"


def _nba_tables(highlight: str) -> list[SportTable]:
    data = _json(f"{STANDINGS}/basketball/nba/standings")
    names = {"Eastern Conference": "Conférence Est", "Western Conference": "Conférence Ouest"}
    tables = []
    for conference in data.get("children", []):
        rows = []
        for entry in conference["standings"]["entries"]:
            s = _stats(entry)
            rows.append((entry, s))
        rows.sort(key=lambda item: (-float(item[1].get("winPercent") or 0),
                                    -int(item[1].get("wins") or 0)))
        tables.append(SportTable(
            title=f"NBA · {names.get(conference['name'], conference['name'])}",
            columns=["Rg", "Équipe", "V", "D", "%", "Écart"],
            rows=[[str(i), e["team"]["displayName"], s.get("wins", ""), s.get("losses", ""),
                   s.get("winPercent", ""), s.get("gamesBehind", "")]
                  for i, (e, s) in enumerate(rows, 1)],
            highlight=highlight,
        ))
    return tables


# --- Point d'entrée -----------------------------------------------------------

def collect_sport(config: dict, now: dt.datetime) -> tuple[SportPage, DataSourceStatus]:
    tz = ZoneInfo(str(config.get("timezone") or "Europe/Paris"))
    today = now.astimezone(tz).date()
    page = SportPage()
    failures: list[str] = []

    sections = (
        ("tennis", _tennis, "Tennis"),
        ("football", _football, "Football"),
        ("nba", _nba, "NBA"),
    )
    for key, collector, label in sections:
        section = config.get(key)
        if not section or not section.get("enabled", True):
            continue
        try:
            result = collector(section, today, tz)
        except Exception as error:  # une discipline en panne n'arrête pas les autres
            failures.append(f"{label} ({type(error).__name__})")
            continue
        if key == "tennis":
            page.today.extend(result)
        elif key == "football":
            page.today.extend(result[0])
            page.tables.extend(result[1])
        else:
            events, recaps, tables, notes = result
            page.today.extend(events)
            page.recaps.extend(recaps)
            page.tables.extend(tables)
            page.notes.extend(notes)

    page.today = page.today[:40]
    page.recaps = page.recaps[:16]
    page.tables = page.tables[:4]
    count = len(page.today) + len(page.recaps)
    if failures and page.is_empty():
        state, detail = DataState.UNAVAILABLE, "ESPN indisponible : " + ", ".join(failures)
    else:
        state = DataState.LIVE
        detail = "ESPN" + (f" (indisponible : {', '.join(failures)})" if failures else "")
    return page, DataSourceStatus(name="Sport", state=state, detail=detail[:240], item_count=count)

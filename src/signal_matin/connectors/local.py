"""Local : éphéméride, actus du coin et sorties du week-end, sans clé API.

- Saint du jour : Nominis (nominis.cef.fr).
- Ce jour-là : Wikipédia en français (événements, naissances, journées).
- Soleil : Open-Meteo ; phase de lune calculée localement.
- Actus : flux RSS filtrés sur une liste de communes.
- Sorties : page « week-end » d'un office de tourisme (fiches iris-etourism).
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import urllib.parse
import urllib.request
from typing import Any

from ..models import (
    DataSourceStatus, DataState, Ephemeris, EphemerisEntry, LocalEvent, NewsItem,
)
from .rss import collect_rss

_HEADERS = {
    "User-Agent": "Signal-Matin/1.0 (+https://github.com/sosoj92/signal-matin)",
    "Accept": "*/*",
}
NOMINIS = "https://nominis.cef.fr/json/nominis.php"
ONTHISDAY = "https://api.wikimedia.org/feed/v1/wikipedia/fr/onthisday/all/{month:02d}/{day:02d}"
SUN = "https://api.open-meteo.com/v1/forecast"

_MONTHS = {
    "janv": 1, "janvier": 1, "févr": 2, "fevr": 2, "février": 2, "mars": 3, "avr": 4,
    "avril": 4, "mai": 5, "juin": 6, "juil": 7, "juillet": 7, "août": 8, "aout": 8,
    "sept": 9, "septembre": 9, "oct": 10, "octobre": 10, "nov": 11, "novembre": 11,
    "déc": 12, "dec": 12, "décembre": 12,
}
_DATE = re.compile(
    r"(\d{1,2})\s+(janv(?:ier)?|févr(?:ier)?|fevr|mars|avr(?:il)?|mai|juin|juil(?:let)?|"
    r"août|aout|sept(?:embre)?|oct(?:obre)?|nov(?:embre)?|déc(?:embre)?|dec)\.?(?:\s+(\d{4}))?",
    re.I,
)


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read(3_000_000)


def _json(url: str) -> Any:
    return json.loads(_get(url))


# --- Éphéméride -----------------------------------------------------------------

_MOON = (
    (0.034, "Nouvelle lune"), (0.216, "Premier croissant"), (0.284, "Premier quartier"),
    (0.466, "Gibbeuse croissante"), (0.534, "Pleine lune"), (0.716, "Gibbeuse décroissante"),
    (0.784, "Dernier quartier"), (0.966, "Dernier croissant"), (1.0, "Nouvelle lune"),
)


def moon_phase(moment: dt.datetime) -> str:
    """Phase de la lune à partir de la nouvelle lune de référence du 6 janvier 2000."""
    reference = dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)
    synodic = 29.530588853
    age = ((moment - reference).total_seconds() / 86400) % synodic / synodic
    return next(name for limit, name in _MOON if age < limit)


def _hour(value: str) -> str:
    moment = dt.datetime.fromisoformat(value)
    return f"{moment.hour}h{moment.minute:02d}"


def _entries(items: list[dict], limit: int) -> list[EphemerisEntry]:
    entries = []
    for item in items:
        text = " ".join(str(item.get("text") or "").split())
        if text and item.get("year") is not None:
            entries.append(EphemerisEntry(year=int(item["year"]), text=text[:300]))
    return entries[:limit]


def collect_ephemeris(config: dict, now: dt.datetime, latitude: float | None,
                      longitude: float | None) -> tuple[Ephemeris, DataSourceStatus]:
    today = now.date()
    ephemeris = Ephemeris(moon=moon_phase(now))
    failures = []
    try:
        data = _json(f"{NOMINIS}?jour={today.day}&mois={today.month}")["response"]
        saints = list((data.get("saints") or {}).get("majeurs", {}).values())
        if saints:
            ephemeris.saint = str(saints[0].get("valeur") or "")[:120]
            ephemeris.saint_note = str(saints[0].get("resume") or "")[:200]
        ephemeris.names = list((data.get("prenoms") or {}).get("majeurs", {}))[:4]
    except Exception:
        failures.append("saint")
    try:
        data = _json(ONTHISDAY.format(month=today.month, day=today.day))
        # « selected » est la sélection éditoriale de Wikipédia : les faits marquants.
        ephemeris.history = _entries(data.get("selected") or data.get("events") or [], 12)
        ephemeris.births = _entries(data.get("births") or [], 60)
        # « Organisation des Nations unies : journée internationale de la non-violence… »
        world_days = []
        for item in data.get("holidays") or []:
            text = " ".join(str(item.get("text") or "").split())
            match = re.search(r"(?i)\b(journée (mondiale|internationale)[^.;(]*)", text)
            if match:
                day = match.group(1).strip().rstrip(",")
                day = re.sub(r"\s+depuis \d{4}$", "", day)
                world_days.append(day[0].upper() + day[1:])
        ephemeris.world_days = world_days[:3]
    except Exception:
        failures.append("Wikipédia")
    if latitude is not None and longitude is not None:
        try:
            query = urllib.parse.urlencode({
                "latitude": latitude, "longitude": longitude, "forecast_days": 1,
                "daily": "sunrise,sunset,daylight_duration",
                "timezone": str(config.get("timezone") or "Europe/Paris"),
            })
            daily = _json(f"{SUN}?{query}")["daily"]
            ephemeris.sunrise = _hour(daily["sunrise"][0])
            ephemeris.sunset = _hour(daily["sunset"][0])
            minutes = round(float(daily["daylight_duration"][0]) / 60)
            ephemeris.daylight = f"{minutes // 60} h {minutes % 60:02d}"
        except Exception:
            failures.append("soleil")
    state = DataState.LIVE if len(failures) < 3 else DataState.UNAVAILABLE
    detail = "Nominis, Wikipédia, Open-Meteo"
    if failures:
        detail += " (manquant : " + ", ".join(failures) + ")"
    return ephemeris, DataSourceStatus(name="Ephemeride", state=state, detail=detail)


# --- Actus locales -------------------------------------------------------------

def collect_local_news(config: dict, now: dt.datetime) -> tuple[list[NewsItem], DataSourceStatus]:
    feeds = config.get("feeds") or []
    places = [str(place) for place in config.get("places") or []]
    items, status = collect_rss(
        feeds, now, limit=60, max_age_hours=int(config.get("max_age_hours") or 36),
        status_name="Actus locales",
    )
    if places:
        # Les premiers lieux de la liste sont les plus proches : ils passent en tête.
        patterns = [re.compile(r"\b" + re.escape(place) + r"\b", re.I) for place in places]

        def rank(item: NewsItem) -> int | None:
            text = f"{item.title} {item.summary}"
            return next((index for index, pattern in enumerate(patterns)
                         if pattern.search(text)), None)

        ranked = [(rank(item), position, item) for position, item in enumerate(items)]
        items = [item for score, _, item in sorted(
            entry for entry in ranked if entry[0] is not None)]
    seen, unique = set(), []
    for item in items:
        key = item.title.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    limit = int(config.get("limit") or 6)
    return unique[:limit], status.model_copy(update={"item_count": len(unique[:limit])})


# --- Sorties du week-end --------------------------------------------------------

def _parse_dates(text: str, year: int) -> list[dt.date]:
    dates = []
    for day, month, found_year in _DATE.findall(text):
        key = month.casefold().rstrip(".")
        month_number = _MONTHS.get(key) or _MONTHS.get(key[:4]) or _MONTHS.get(key[:3])
        if not month_number:
            continue
        try:
            dates.append(dt.date(int(found_year or year), month_number, int(day)))
        except ValueError:
            continue
    return dates


def parse_tourism_events(page: str, year: int) -> list[LocalEvent]:
    """Fiches « iris-etourism » : titre et catégorie en attributs, dates et commune en texte."""
    events = []
    for card in re.split(r"(?=<[^>]+data-layer-wpet-offer-title=)", page)[1:]:
        title = re.search(r'data-layer-wpet-offer-title="([^"]*)"', card)
        if not title:
            continue
        body = re.sub(r"(?is)<(script|style|svg|img)[^>]*?>.*?(</\1>|$)", " ", card[:8000])
        text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", body)).split())
        dates = _parse_dates(text[:400], year)
        commune = re.search(r"\b([A-ZÉÈÀÂÎÔÛÇ][A-ZÉÈÀÂÎÔÛÇ' -]{2,40})\b(?=\s|$)", text[:500])
        link = re.search(r'href="(https?://[^"]+)"', card)
        events.append(LocalEvent(
            title=html.unescape(title.group(1)).strip()[:160] or "Événement",
            start=min(dates) if dates else None,
            end=max(dates) if dates else None,
            place=(commune.group(1).strip().title() if commune else "")[:80],
            category="Exposition" if text.startswith("Exposition") else "",
            url=link.group(1) if link else None,
        ))
    return events


def collect_local_events(config: dict, now: dt.datetime) -> tuple[list[LocalEvent], DataSourceStatus]:
    today = now.date()
    days = [int(day) for day in config.get("weekdays", [4, 5])]
    if today.weekday() not in days:
        return [], DataSourceStatus(name="Sorties", state=DataState.DISABLED,
                                    detail="Affichées le vendredi et le samedi.")
    url = str(config.get("url") or "")
    if not url:
        return [], DataSourceStatus(name="Sorties", state=DataState.DISABLED,
                                    detail="Aucune page d'agenda configurée.")
    try:
        page = _get(url).decode("utf-8", errors="replace")
    except Exception as error:
        return [], DataSourceStatus(name="Sorties", state=DataState.UNAVAILABLE,
                                    detail=f"Agenda indisponible : {type(error).__name__}.")
    # Du jour jusqu'au dimanche : on refait le filtre, la page mélange d'autres rubriques.
    sunday = today + dt.timedelta(days=6 - today.weekday())
    seen, weekend = set(), []
    for event in parse_tourism_events(page, today.year):
        if event.start is None or event.title in seen:
            continue
        if event.start <= sunday and (event.end or event.start) >= today:
            seen.add(event.title)
            weekend.append(event)
    # Les rendez-vous ponctuels d'abord, les longues expositions ensuite.
    weekend.sort(key=lambda e: (bool(e.category), ((e.end or e.start) - e.start).days, e.start))
    limit = int(config.get("limit") or 8)
    return weekend[:limit], DataSourceStatus(
        name="Sorties", state=DataState.LIVE if weekend else DataState.UNAVAILABLE,
        detail=f"{len(weekend)} événement(s) jusqu'à dimanche", item_count=len(weekend[:limit]))

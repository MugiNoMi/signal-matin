"""Marchés : cours, palmarès de la veille et agenda macro, sans clé API.

Cours et palmarès viennent de Yahoo Finance, l'agenda de ForexFactory.
Ce sont des données publiques non officielles, à titre d'information.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from zoneinfo import ZoneInfo

from ..models import (
    DataSourceStatus, DataState, MacroEvent, MarketMover, MarketMovers, MarketQuote,
    MarketsPage,
)

CHART = "https://query1.finance.yahoo.com/v8/finance/chart/"
SCREENER = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
CALENDAR = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_HEADERS = {
    "User-Agent": "Signal-Matin/1.0 (+https://github.com/sosoj92/signal-matin)",
    "Accept": "*/*",
}

DEFAULT_QUOTES = [
    {"symbol": "^FCHI", "name": "CAC 40"},
    {"symbol": "^GSPC", "name": "S&P 500"},
    {"symbol": "EURUSD=X", "name": "EUR/USD", "decimals": 4},
    {"symbol": "GC=F", "name": "Or", "unit": "$"},
    {"symbol": "BZ=F", "name": "Brent", "unit": "$"},
    {"symbol": "BTC-USD", "name": "Bitcoin", "unit": "$", "crypto": True},
    {"symbol": "ETH-USD", "name": "Ethereum", "unit": "$", "crypto": True},
    {"symbol": "BNB-USD", "name": "BNB", "unit": "$", "crypto": True},
]

# Composition du CAC 40 (à ajuster dans config.yaml si l'indice évolue).
CAC40 = {
    "AC.PA": "Accor", "AI.PA": "Air Liquide", "AIR.PA": "Airbus", "MT.AS": "ArcelorMittal",
    "CS.PA": "AXA", "BNP.PA": "BNP Paribas", "EN.PA": "Bouygues", "BVI.PA": "Bureau Veritas",
    "CAP.PA": "Capgemini", "CA.PA": "Carrefour", "ACA.PA": "Crédit Agricole", "BN.PA": "Danone",
    "DSY.PA": "Dassault Systèmes", "EDEN.PA": "Edenred", "ENGI.PA": "Engie",
    "EL.PA": "EssilorLuxottica", "ERF.PA": "Eurofins", "RMS.PA": "Hermès", "KER.PA": "Kering",
    "OR.PA": "L'Oréal", "LR.PA": "Legrand", "MC.PA": "LVMH", "ML.PA": "Michelin",
    "ORA.PA": "Orange", "RI.PA": "Pernod Ricard", "PUB.PA": "Publicis", "RNO.PA": "Renault",
    "SAF.PA": "Safran", "SGO.PA": "Saint-Gobain", "SAN.PA": "Sanofi", "SU.PA": "Schneider Electric",
    "GLE.PA": "Société Générale", "STLAP.PA": "Stellantis", "STMPA.PA": "STMicroelectronics",
    "TEP.PA": "Teleperformance", "HO.PA": "Thales", "TTE.PA": "TotalEnergies",
    "URW.PA": "Unibail-Rodamco-Westfield", "VIE.PA": "Veolia", "DG.PA": "Vinci",
}

_MACRO_FR = {
    "non-farm employment change": "Créations d'emplois non agricoles (NFP)",
    "unemployment rate": "Taux de chômage",
    "cpi m/m": "Inflation (IPC) sur un mois",
    "cpi y/y": "Inflation (IPC) sur un an",
    "core cpi m/m": "Inflation sous-jacente sur un mois",
    "core pce price index m/m": "Inflation PCE sous-jacente sur un mois",
    "ppi m/m": "Prix à la production sur un mois",
    "federal funds rate": "Décision de taux de la Fed",
    "fomc statement": "Communiqué de la Fed",
    "fomc press conference": "Conférence de presse de la Fed",
    "fomc meeting minutes": "Compte rendu de la Fed",
    "main refinancing rate": "Décision de taux de la BCE",
    "monetary policy statement": "Communiqué de politique monétaire",
    "ecb press conference": "Conférence de presse de la BCE",
    "advance gdp q/q": "PIB (première estimation)",
    "gdp q/q": "PIB sur un trimestre",
    "prelim gdp q/q": "PIB (estimation préliminaire)",
    "retail sales m/m": "Ventes au détail sur un mois",
    "core retail sales m/m": "Ventes au détail hors auto",
    "ism manufacturing pmi": "Indice ISM manufacturier",
    "ism services pmi": "Indice ISM des services",
    "jolts job openings": "Offres d'emploi (JOLTS)",
    "unemployment claims": "Inscriptions hebdomadaires au chômage",
    "cb consumer confidence": "Confiance des consommateurs",
    "german prelim cpi m/m": "Inflation allemande (préliminaire)",
    "cpi flash estimate y/y": "Inflation zone euro (estimation flash)",
    "core cpi flash estimate y/y": "Inflation sous-jacente zone euro (flash)",
}
_COUNTRIES = {"USD": "États-Unis", "EUR": "Zone euro", "GBP": "Royaume-Uni",
              "JPY": "Japon", "CNY": "Chine", "CHF": "Suisse"}
_IMPACT = {"High": "Fort", "Medium": "Moyen", "Low": "Faible"}


def _json(url: str) -> dict[str, Any] | list[Any]:
    request = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def _chart(symbol: str, range_: str, interval: str = "1d") -> dict[str, Any]:
    query = urllib.parse.urlencode({"range": range_, "interval": interval})
    data = _json(f"{CHART}{urllib.parse.quote(symbol)}?{query}")
    return data["chart"]["result"][0]


def _closes(result: dict[str, Any], before: dt.date | None = None) -> list[float]:
    """Clôtures, en ignorant la séance du jour même (pas encore terminée à l'aube)."""
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    exchange_tz = ZoneInfo(result.get("meta", {}).get("exchangeTimezoneName") or "UTC")
    values = []
    for stamp, value in zip(result.get("timestamp") or [], quote.get("close") or []):
        if value is None:
            continue
        if before and dt.datetime.fromtimestamp(stamp, exchange_tz).date() >= before:
            continue
        values.append(float(value))
    return values


def _pct(new: float, old: float | None) -> float | None:
    if not old:
        return None
    return round((new / old - 1) * 100, 2)


def _quote(spec: dict[str, Any], today: dt.date) -> MarketQuote:
    symbol = spec["symbol"]
    ytd = _chart(symbol, "ytd")
    meta = ytd["meta"]
    price = float(meta["regularMarketPrice"])
    closes = _closes(ytd, before=today)
    if spec.get("crypto"):
        # Marché continu : variation sur les 24 dernières heures.
        hourly = _closes(_chart(symbol, "2d", "1h"))
        day = _pct(price, hourly[-25] if len(hourly) >= 25 else (hourly[0] if hourly else None))
    else:
        day = _pct(closes[-1], closes[-2]) if len(closes) >= 2 else None
        price = closes[-1] if closes else price
    return MarketQuote(
        name=str(spec.get("name") or meta.get("shortName") or symbol), symbol=symbol,
        price=price, unit=str(spec.get("unit") or ""), decimals=int(spec.get("decimals", 2)),
        change_pct=day, ytd_pct=_pct(price, meta.get("chartPreviousClose")),
        crypto=bool(spec.get("crypto")),
    )


def _session_move(symbol: str, name: str, today: dt.date) -> MarketMover | None:
    result = _chart(symbol, "5d")
    closes = _closes(result, before=today)
    if len(closes) < 2:
        return None
    return MarketMover(name=name, symbol=symbol, price=closes[-1],
                       change_pct=_pct(closes[-1], closes[-2]) or 0.0)


def _index_movers(title: str, members: dict[str, str], count: int,
                  today: dt.date) -> MarketMovers:
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(
            lambda item: _safe(_session_move, item[0], item[1], today), members.items()))
    moves = sorted((m for m in results if m), key=lambda m: m.change_pct, reverse=True)
    if len(moves) < len(members) // 2:
        raise RuntimeError(f"{title} : trop peu de cours reçus ({len(moves)}/{len(members)})")
    losers = [m for m in reversed(moves) if m.change_pct < 0][:count]
    return MarketMovers(title=title, gainers=[m for m in moves if m.change_pct > 0][:count],
                        losers=losers)


def _safe(function, *args):
    try:
        return function(*args)
    except Exception:
        return None


def _us_movers(count: int) -> MarketMovers:
    def screen(name: str) -> list[MarketMover]:
        query = urllib.parse.urlencode({"scrIds": name, "count": count})
        quotes = _json(f"{SCREENER}?{query}")["finance"]["result"][0]["quotes"]
        return [MarketMover(
            name=str(q.get("shortName") or q.get("longName") or q["symbol"]), symbol=q["symbol"],
            price=float(q.get("regularMarketPrice") or 0),
            change_pct=round(float(q.get("regularMarketChangePercent") or 0), 2),
        ) for q in quotes[:count]]
    return MarketMovers(title="États-Unis", gainers=screen("day_gainers"), losers=screen("day_losers"))


def _macro(config: dict, today: dt.date, tz: ZoneInfo) -> list[MacroEvent]:
    countries = set(config.get("countries") or ["USD", "EUR"])
    impacts = set(config.get("impact") or ["High", "Medium"])
    events = []
    for item in _json(CALENDAR):
        if item.get("country") not in countries or item.get("impact") not in impacts:
            continue
        when = dt.datetime.fromisoformat(item["date"]).astimezone(tz)
        if when.date() != today:
            continue
        title = str(item.get("title") or "").strip()
        all_day = when.hour == 0 and when.minute == 0
        events.append(MacroEvent(
            time="Journée" if all_day else f"{when.hour}h{when.minute:02d}",
            country=_COUNTRIES.get(item["country"], item["country"]),
            title=_MACRO_FR.get(title.casefold(), title),
            impact=_IMPACT.get(item.get("impact"), item.get("impact", "")),
            forecast=str(item.get("forecast") or ""), previous=str(item.get("previous") or ""),
        ))
    return sorted(events, key=lambda e: (e.time == "Journée", e.time.zfill(5)))[:12]


def collect_markets(config: dict, now: dt.datetime) -> tuple[MarketsPage, DataSourceStatus]:
    tz = ZoneInfo(str(config.get("timezone") or "Europe/Paris"))
    today = now.astimezone(tz).date()
    page = MarketsPage()
    failures: list[str] = []

    specs = config.get("quotes") or DEFAULT_QUOTES
    with ThreadPoolExecutor(max_workers=8) as pool:
        quotes = list(pool.map(lambda spec: _safe(_quote, spec, today), specs))
    page.quotes = [q for q in quotes if q]
    if len(page.quotes) < len(specs):
        missing = [s["symbol"] for s, q in zip(specs, quotes) if not q]
        failures.append("cours " + ", ".join(missing))

    movers = config.get("movers") or {}
    count = int(movers.get("count") or 5)
    if movers.get("cac40", True):
        members = movers.get("cac40_members") or CAC40
        result = _safe(_index_movers, "CAC 40", members, count, today)
        if result:
            page.movers.append(result)
        else:
            failures.append("palmarès CAC 40")
    if movers.get("us", True):
        result = _safe(_us_movers, count)
        if result:
            page.movers.append(result)
        else:
            failures.append("palmarès US")

    macro = config.get("macro") or {}
    if macro.get("enabled", True):
        events = _safe(_macro, macro, today, tz)
        if events is None:
            failures.append("agenda macro")
        else:
            page.agenda = events

    count_items = len(page.quotes) + sum(len(m.gainers) + len(m.losers) for m in page.movers)
    if page.is_empty():
        return page, DataSourceStatus(
            name="Marchés", state=DataState.UNAVAILABLE,
            detail=("Indisponible : " + ", ".join(failures))[:240])
    detail = "Yahoo Finance, ForexFactory"
    if failures:
        detail += " (manquant : " + ", ".join(failures) + ")"
    return page, DataSourceStatus(name="Marchés", state=DataState.LIVE,
                                  detail=detail[:240], item_count=count_items)

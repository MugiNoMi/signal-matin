"""Rédaction facultative par Claude : édito, résumés et mises en perspective.

Claude ne reçoit que ce que l'édition contient déjà (titres et extraits RSS,
cours et palmarès) et n'a pas le droit d'y ajouter des faits. La clé
ANTHROPIC_API_KEY reste dans .env. Si l'appel échoue, l'édition part telle
quelle, sans texte généré.
"""
from __future__ import annotations

import json
import os
from typing import Any

from .models import DataSourceStatus, DataState, EditorialBlock, MorningEdition, NewsItem

DEFAULT_MODEL = "claude-opus-5-5"

TONES = {
    "complice": (
        "Tu tutoies le lecteur, sur un ton direct et vivant, comme un ami très bien informé "
        "qui résume l'actualité au petit-déjeuner. Chaleureux mais jamais familier ni racoleur."
    ),
    "serieux": "Style d'un quotidien de référence : neutre, factuel, sobre, vouvoiement.",
    "concis": "Style télégraphique : l'essentiel en un minimum de mots, sans effet de style.",
}

SYSTEM = """Tu es le rédacteur en chef de « {title} », un journal personnel imprimé chaque matin \
sur une feuille A4 pour {reader}. Tu reçois les dépêches du jour (titres et extraits de flux RSS), \
les cours de marché et les palmarès de la veille, au format JSON.

Ton travail :
1. Un édito court : un titre de moins de 70 caractères et un texte de 5 à 6 phrases \
(700 caractères au maximum, il doit tenir en bas de la une) qui relie les trois ou quatre \
informations majeures du matin et dit ce qu'il faut en retenir.
2. Pour chaque dépêche, un résumé propre de 2 à 3 phrases, puis une phrase « pourquoi c'est \
important » qui donne l'enjeu ou ce que ça change concrètement.
3. Une courte lecture de la veille tech et IA (3 à 4 phrases).
4. Une courte lecture des marchés (3 à 4 phrases) : ce qui a bougé et les explications que les \
dépêches permettent d'avancer.

Règles impératives :
- N'utilise que les informations fournies. N'invente aucun fait, chiffre, citation ni cause. \
Si un extrait est trop mince pour conclure, dis-le simplement ou reste général.
- Pour les marchés, ne présente jamais une explication comme certaine si aucune dépêche ne la \
donne, et ne donne aucun conseil d'investissement.
- Écris en français, pour être lu sur papier : pas de liens, pas de markdown, pas d'emoji.
- Reprends exactement les identifiants « id » reçus.

Ton : {tone}"""

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "editorial": {
            "type": "object",
            "properties": {"title": {"type": "string"}, "text": {"type": "string"}},
            "required": ["title", "text"],
            "additionalProperties": False,
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "summary": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                },
                "required": ["id", "summary", "why_it_matters"],
                "additionalProperties": False,
            },
        },
        "tech_insight": {"type": "string"},
        "markets_insight": {"type": "string"},
    },
    "required": ["editorial", "items", "tech_insight", "markets_insight"],
    "additionalProperties": False,
}


def _articles(edition: MorningEdition) -> dict[str, NewsItem]:
    """Dépêches à réécrire, avec un identifiant stable par position."""
    articles: dict[str, NewsItem] = {}
    if edition.news.lead:
        articles["n0"] = edition.news.lead
    for index, item in enumerate(edition.news.all_secondary(), 1):
        articles[f"n{index}"] = item
    for index, item in enumerate(edition.tech_news, 1):
        articles[f"t{index}"] = item
    return articles


def _payload(edition: MorningEdition, articles: dict[str, NewsItem]) -> str:
    markets = edition.markets
    data = {
        "date": edition.edition.date.isoformat(),
        "depeches": [
            {"id": key, "rubrique": item.category, "source": item.source.name,
             "titre": item.title, "extrait": item.expanded_summary or item.summary}
            for key, item in articles.items()
        ],
        "marches": {
            "cours": [{"actif": q.name, "variation_veille_pct": q.change_pct,
                       "depuis_janvier_pct": q.ytd_pct} for q in markets.quotes],
            "palmares": [{"marche": m.title,
                          "hausses": [[x.name, x.change_pct] for x in m.gainers],
                          "baisses": [[x.name, x.change_pct] for x in m.losers]}
                         for m in markets.movers],
            "agenda": [f"{e.time} {e.country} : {e.title}" for e in markets.agenda],
        },
    }
    return json.dumps(data, ensure_ascii=False)


def _apply(edition: MorningEdition, articles: dict[str, NewsItem], result: dict[str, Any],
           author: str) -> MorningEdition:
    rewritten: dict[int, NewsItem] = {}
    for entry in result.get("items", []):
        item = articles.get(entry.get("id", ""))
        summary = " ".join(str(entry.get("summary") or "").split())
        if item is None or not summary:
            continue
        rewritten[id(item)] = item.model_copy(update={
            "summary": summary[:1600],
            "expanded_summary": "",
            "why_it_matters": " ".join(str(entry.get("why_it_matters") or "").split())[:400],
        })

    def swap(item: NewsItem) -> NewsItem:
        return rewritten.get(id(item), item)

    news = edition.news
    news = news.model_copy(update={
        "lead": swap(news.lead) if news.lead else None,
        **{group: [swap(item) for item in getattr(news, group)]
           for group in ("world", "france", "economy", "society", "science", "culture")},
    })
    tech_news = [swap(item) for item in edition.tech_news]
    # Le résumé « IA & tech » des pages courtes reprend les textes réécrits.
    by_title = {item.title: item for item in tech_news}
    tech = [digest.model_copy(update={"summary": by_title[digest.title].summary})
            if digest.title in by_title else digest for digest in edition.tech]

    editorial = result.get("editorial") or {}
    block = EditorialBlock(
        title=str(editorial.get("title") or "L'essentiel du matin").strip()[:140],
        text=" ".join(str(editorial.get("text") or "").split())[:1400] or "–",
        tech_insight=" ".join(str(result.get("tech_insight") or "").split())[:900],
        markets_insight=" ".join(str(result.get("markets_insight") or "").split())[:900],
        author=author,
    )
    return edition.model_copy(update={
        "news": news, "tech_news": tech_news, "tech": tech, "editorial": block,
    })


def _status(state: DataState, detail: str, count: int = 0) -> DataSourceStatus:
    return DataSourceStatus(name="Redaction IA", state=state, detail=detail[:240],
                            item_count=count)


def rediger_avec_claude(edition: MorningEdition, config: dict,
                        client: Any = None) -> tuple[MorningEdition, DataSourceStatus]:
    articles = _articles(edition)
    if not articles:
        return edition, _status(DataState.UNAVAILABLE, "Aucune dépêche à résumer.")
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return edition, _status(DataState.UNAVAILABLE,
                                    "Clé ANTHROPIC_API_KEY absente du fichier .env.")
        try:
            import anthropic
        except ImportError:
            return edition, _status(DataState.UNAVAILABLE,
                                    "SDK anthropic absent : installer l'extra [ai].")
        client = anthropic.Anthropic(timeout=300.0)

    model = str(config.get("model") or DEFAULT_MODEL)
    tone = TONES.get(str(config.get("tone") or "complice"), TONES["complice"])
    system = SYSTEM.format(
        title=edition.edition.title, reader=str(config.get("reader") or "son lecteur"),
        tone=tone,
    )
    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            # Si un filtre de sécurité refuse la requête, l'API la rejoue sur le
            # modèle de repli recommandé au lieu de laisser le journal sans texte.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={
                "effort": str(config.get("effort") or "medium"),
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
            system=system,
            messages=[{"role": "user", "content": _payload(edition, articles)}],
        )
    except Exception as error:  # l'édition sort sans rédaction plutôt que pas du tout
        return edition, _status(DataState.UNAVAILABLE,
                                f"Claude indisponible : {type(error).__name__}.")
    if response.stop_reason == "refusal":
        return edition, _status(DataState.UNAVAILABLE, "Claude a refusé la requête.")
    if response.stop_reason == "max_tokens":
        return edition, _status(DataState.UNAVAILABLE, "Réponse de Claude tronquée.")
    text = next((block.text for block in response.content if block.type == "text"), "")
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        return edition, _status(DataState.UNAVAILABLE, "Réponse de Claude illisible.")
    served_by = getattr(response, "model", model) or model
    updated = _apply(edition, articles, result, author=served_by)
    return updated, _status(DataState.LIVE, f"Rédigé par {served_by}",
                            count=len(result.get("items", [])))

import datetime as dt
import json
from types import SimpleNamespace

from signal_matin.editorial import SCHEMA, rediger_avec_claude
from signal_matin.mock_data import construire_demo
from signal_matin.models import DataState
from signal_matin.normalizer import normaliser_edition
from signal_matin.renderer import render_html


def _edition():
    edition = construire_demo(dt.date(2026, 9, 29))
    return edition.model_copy(update={"editorial": None})


class FakeClient:
    def __init__(self, payload=None, stop_reason="end_turn", error=None):
        self.calls = []
        self.payload, self.stop_reason, self.error = payload, stop_reason, error
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        text = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return SimpleNamespace(stop_reason=self.stop_reason, model="claude-opus-5-5",
                               content=[SimpleNamespace(type="text", text=text)])


def _answer(edition):
    ids = ["n0", "n1", "t1"]
    return {
        "editorial": {"title": "Ce matin", "text": "Trois infos à retenir."},
        "items": [{"id": i, "summary": f"Résumé {i}.", "why_it_matters": f"Enjeu {i}.", "long_text": "", "print": True}
                  for i in ids] + [{"id": "inconnu", "summary": "x", "why_it_matters": "y"}],
        "tech_insight": "La tech bouge.",
        "markets_insight": "Les marchés hésitent.",
    }


def test_claude_rewrites_items_and_adds_editorial():
    edition = _edition()
    client = FakeClient(_answer(edition))
    updated, status = rediger_avec_claude(edition, {"tone": "complice"}, client=client)

    assert status.state == DataState.LIVE and status.detail == "Rédigé par claude-opus-5-5"
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": SCHEMA}
    assert "tutoies" in call["system"]
    sent = json.loads(call["messages"][0]["content"])
    assert sent["depeches"][0]["id"] == "n0" and sent["marches"]["cours"]

    assert updated.news.lead.summary == "Résumé n0."
    assert updated.news.lead.why_it_matters == "Enjeu n0."
    assert updated.news.lead.expanded_summary == ""
    assert updated.news.all_secondary()[0].summary == "Résumé n1."
    assert updated.tech_news[0].summary == "Résumé t1."
    assert updated.tech[0].summary == "Résumé t1."
    assert updated.editorial.title == "Ce matin"
    assert updated.editorial.markets_insight == "Les marchés hésitent."

    html = render_html(normaliser_edition(updated, mode="compact"))
    assert "L’édito du matin" in html and "Pourquoi c’est important." in html
    assert "La lecture des marchés" in html


def test_failures_keep_the_original_edition():
    edition = _edition()
    for client, detail in (
        (FakeClient(error=RuntimeError("réseau")), "Claude indisponible : RuntimeError."),
        (FakeClient({}, stop_reason="refusal"), "Claude a refusé la requête."),
        (FakeClient({}, stop_reason="max_tokens"), "Réponse de Claude tronquée."),
        (FakeClient("pas du json"), "Réponse de Claude illisible."),
    ):
        updated, status = rediger_avec_claude(edition, {}, client=client)
        assert updated is edition
        assert status.state == DataState.UNAVAILABLE and status.detail == detail


def test_missing_api_key_is_reported(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    edition = _edition()
    updated, status = rediger_avec_claude(edition, {})
    assert updated is edition and "ANTHROPIC_API_KEY" in status.detail


def test_front_briefs_get_full_text_and_a_capped_long_version(monkeypatch):
    from signal_matin import editorial

    monkeypatch.setattr(editorial, "fetch_article_text",
                        lambda url: "Texte complet de l'article. " * 40)
    edition = _edition()
    long_text = "\n\n".join(["Premier paragraphe. " * 30, "Deuxième paragraphe. " * 30,
                             "Troisième paragraphe. " * 30])
    answer = _answer(edition)
    answer["items"] = [{"id": "n1", "summary": "Résumé.", "why_it_matters": "Enjeu.",
                        "long_text": long_text, "print": True}]
    client = FakeClient(answer)
    updated, _ = rediger_avec_claude(edition, {}, client=client)

    sent = json.loads(client.calls[0]["messages"][0]["content"])["depeches"]
    with_text = [d["id"] for d in sent if "texte_complet" in d]
    assert with_text == ["n1", "n2", "n3"]  # les trois brèves de la une, pas la une
    developed = updated.news.all_secondary()[0].expanded_summary
    assert len(developed) <= editorial.LONG_TEXT_MAX and developed.endswith(".")
    assert developed.startswith("Premier paragraphe.") and "\n\n" in developed

    html = render_html(normaliser_edition(updated, mode="compact"))
    assert 'class="long-read"' in html


def test_items_without_substance_are_dropped_but_never_the_lead():
    edition = _edition()
    answer = _answer(edition)
    answer["items"] = [
        {"id": "n0", "summary": "Une.", "why_it_matters": "", "long_text": "", "print": False},
        {"id": "n2", "summary": "Émission.", "why_it_matters": "", "long_text": "", "print": False},
        {"id": "t1", "summary": "Promo.", "why_it_matters": "", "long_text": "", "print": False},
    ]
    dropped_news = edition.news.all_secondary()[1].title
    dropped_tech = edition.tech_news[0].title
    updated, _ = rediger_avec_claude(edition, {}, client=FakeClient(answer))
    assert updated.news.lead is not None and updated.news.lead.summary == "Une."
    assert dropped_news not in [item.title for item in updated.news.all_secondary()]
    assert len(updated.news.all_secondary()) == len(edition.news.all_secondary()) - 1
    assert dropped_tech not in [item.title for item in updated.tech_news]
    assert dropped_tech not in [digest.title for digest in updated.tech]

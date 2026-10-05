import datetime as dt

import pytest

from signal_matin import cli, pipeline
from signal_matin.mock_data import construire_demo
from signal_matin.models import FAILED_SECTION, DataSourceStatus, DataState
from signal_matin.normalizer import normaliser_edition
from signal_matin.renderer import render_html

NOW = dt.datetime(2026, 10, 5, 6, 50, tzinfo=dt.UTC)
BASE = {"modules": {"weather": False, "calendar": False, "tasks": False, "news": False,
                    "tech": False, "sport": True, "markets": True}}


def test_a_crashing_section_is_removed_and_reported(monkeypatch, tmp_path):
    def broken(config, now):
        raise KeyError("champ inattendu")

    monkeypatch.setattr(pipeline, "collect_sport", broken)
    monkeypatch.setattr(pipeline, "collect_markets", lambda config, now: (
        pipeline.MarketsPage(), DataSourceStatus(name="Marches", state=DataState.LIVE)))
    edition = pipeline.build_live(BASE, now=NOW, root=tmp_path)
    sport = next(source for source in edition.sources if source.name == "Sport")
    assert sport.state == DataState.UNAVAILABLE and sport.detail.startswith(FAILED_SECTION)
    assert "KeyError" in sport.detail and edition.sport.is_empty()
    assert any(source.name == "Marches" and source.state == DataState.LIVE
               for source in edition.sources)


def test_front_page_lists_removed_sections():
    edition = construire_demo(dt.date(2026, 10, 5))
    edition = edition.model_copy(update={"sources": [*edition.sources, DataSourceStatus(
        name="Sport", state=DataState.UNAVAILABLE, detail=f"{FAILED_SECTION} ce matin.")]})
    html = render_html(normaliser_edition(edition, mode="compact"))
    assert "Indisponible ce matin à la suite d’un incident : Sport." in html


def test_minimal_config_keeps_only_core_sections():
    config = {"modules": {"weather": True, "news": True, "sport": True, "ai": True}, "demo": False}
    modules = cli._minimal_config(config)["modules"]
    assert modules["weather"] and modules["news"]
    assert not modules["sport"] and not modules["ai"] and not modules["mail"]


@pytest.fixture
def live_config(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("demo: false\nemail:\n  username: a@b.c\n  password: x\n"
                    "  printer_to: [p@hpeprint.com]\n  copy_to: [moi@example.org]\n",
                    encoding="utf-8")
    return str(path)


def test_failed_full_edition_falls_back_to_reduced_one(monkeypatch, live_config, tmp_path):
    sent, runs = [], []
    pdf = tmp_path / "edition.pdf"

    def produce(args, config):
        runs.append((config.get("modules") or {}).get("ai", True))
        if len(runs) == 1:
            raise ValueError("titre trop long")
        pdf.write_bytes(b"%PDF-1.7 version reduite")
        return 0

    monkeypatch.setattr(cli, "_produce", produce)
    monkeypatch.setattr(cli, "send", lambda settings, messages: sent.extend(messages))
    assert cli.main(["generate", "--email", "--config", live_config, "--output", str(pdf)]) == 0
    assert runs == [True, False]  # complète, puis réduite sans IA
    printer, copy = sent
    assert printer["To"] == "p@hpeprint.com"
    assert "Édition réduite" in copy.get_body(("plain",)).get_content()


def test_alert_only_when_nothing_could_be_produced(monkeypatch, live_config):
    sent = []

    def produce(args, config):
        raise ValueError("panne totale")

    monkeypatch.setattr(cli, "_produce", produce)
    monkeypatch.setattr(cli, "send", lambda settings, messages: sent.extend(messages))
    with pytest.raises(ValueError, match="panne totale"):
        cli.main(["generate", "--email", "--config", live_config])
    assert [message["Subject"] for message in sent] == ["Signal Matin — échec de l'édition"]

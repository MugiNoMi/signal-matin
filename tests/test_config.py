from signal_matin import cli
from signal_matin.config import load_config, setting


def test_environment_values_are_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("SIGNAL_TEST_TOKEN", "local-value")
    path = tmp_path / "config.yaml"
    path.write_text("service:\n  token: '${SIGNAL_TEST_TOKEN}'\n", encoding="utf-8")
    config = load_config(path)
    assert setting(config, "service.token") == "local-value"


def test_paper_density_from_config_applies_when_mode_is_auto(tmp_path, monkeypatch):
    from signal_matin import cli

    path = tmp_path / "config.yaml"
    path.write_text("paper:\n  density: compact\n", encoding="utf-8")
    seen = {}
    monkeypatch.setattr(cli, "_produce", lambda args, config: seen.setdefault("mode", args.mode) and 0)
    cli.main(["generate", "--demo", "--config", str(path)])
    assert seen["mode"] == "compact"
    seen.clear()
    cli.main(["generate", "--demo", "--mode", "standard", "--config", str(path)])
    assert seen["mode"] == "standard"


def test_generate_still_produces_a_pdf_when_a_page_overflows(tmp_path, monkeypatch):
    calls = []

    def fake_pdf(edition, pdf_path, html_path=None, verifier_debordement=True):
        calls.append(verifier_debordement)
        if verifier_debordement:
            raise RuntimeError("Contenu trop long sur les pages : 5")
        return pdf_path

    monkeypatch.setattr(cli, "generer_pdf", fake_pdf)
    monkeypatch.setattr(cli, "write_html", lambda edition, path: path)
    monkeypatch.setattr(cli, "ecrire_edition", lambda edition, path: path)
    assert cli.main(["generate", "--demo", "--output", str(tmp_path / "x.pdf")]) == 0
    assert calls == [True, False]

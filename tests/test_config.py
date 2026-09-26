from signal_matin.config import load_config, setting


def test_environment_values_are_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("SIGNAL_TEST_TOKEN", "local-value")
    path = tmp_path / "config.yaml"
    path.write_text("service:\n  token: '${SIGNAL_TEST_TOKEN}'\n", encoding="utf-8")
    config = load_config(path)
    assert setting(config, "service.token") == "local-value"

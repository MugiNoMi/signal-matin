import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest


@pytest.fixture(autouse=True)
def _no_article_download(monkeypatch):
    """Les tests n'ouvrent jamais de vraie page d'article."""
    from signal_matin import editorial

    monkeypatch.setattr(editorial, "fetch_article_text", lambda url: "")

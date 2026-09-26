"""Point d'entree simple, compatible avec les commandes du README."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from signal_matin.cli import main  # noqa: E402


def _legacy(argv: list[str]) -> list[str]:
    mapping = {"--preview": "preview", "--generate": "generate", "--print": "print"}
    for flag, command in mapping.items():
        if flag in argv:
            return [command, *[item for item in argv if item != flag]]
    return argv or ["preview"]


if __name__ == "__main__":
    raise SystemExit(main(_legacy(sys.argv[1:])))

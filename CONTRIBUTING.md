# Contribuer à Signal Matin

Merci de contribuer. Le projet privilégie les changements petits, testables et
compatibles avec une installation sans compte externe.

## Installation de développement

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
playwright install chromium
pytest
```

## Règles

- aucune donnée personnelle, clé, URL privée ou sortie quotidienne dans Git ;
- aucun connecteur ne doit être importé par le renderer ;
- toute source est facultative et doit échouer proprement ;
- les exemples et tests utilisent uniquement des données fictives ;
- aucune impression automatique pendant l'installation ou les tests ;
- toute modification visuelle est vérifiée en PDF A4 dans les trois densités.

## Pull requests

Décris le problème, la solution et les tests effectués. Pour un changement de
design, joins une capture avant/après. Pour un nouveau connecteur, documente son
périmètre, ses permissions et les fichiers secrets à ignorer.

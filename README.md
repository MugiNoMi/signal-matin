# Signal Matin

Un quotidien personnel A4, genere chaque matin pour commencer la journee sans
ouvrir un fil d'actualite. Signal Matin transforme des sources modulaires en un
petit journal monochrome, editorial et directement imprimable.

![Apercu de la une](docs/images/demo-page-1.png)

## Pourquoi

Le telephone melange les informations utiles, les notifications et le contenu
infini. Signal Matin propose l'inverse : une edition finie, hierarchisee et
calme, avec seulement les informations choisies.

- A4 portrait, noir et blanc et recto verso possible ;
- vraie composition de journal : masthead, colonnes, filets, brèves et dossiers ;
- meteo, agenda, priorites, actualites, tech, veille et recommandations ;
- articles classes en bref, secondaire, developpe et focus ;
- pages supplementaires creees selon la quantite de contenu ;
- mots croises, vocabulaire, quiz et calcul mental generes localement ;
- trois densites : `compact`, `standard`, `extended` ;
- aucune API obligatoire pour essayer le projet.

## Quick start

Prérequis : Python 3.11 ou plus recent.

```bash
git clone https://github.com/sosoj92/signal-matin.git
cd signal-matin
python -m venv .venv
```

Active ensuite l'environnement :

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

Puis :

```bash
pip install -r requirements.txt
playwright install chromium
copy config.example.yaml config.yaml   # Windows
# cp config.example.yaml config.yaml   # macOS / Linux
python main.py --preview
```

Le fichier d'exemple démarre en mode `demo: true` : la première preview est donc
immédiate, complète et entièrement fictive.

## Commandes

Les commandes simples demandées par le projet sont disponibles :

```bash
python main.py --preview
python main.py --generate
python main.py --print
```

La CLI installable offre aussi une forme plus explicite :

```bash
signal-matin preview --demo
signal-matin generate --mode standard
signal-matin data --live
signal-matin print --live --printer "Nom exact" --duplex --confirm
```

`print` ne lance jamais une impression sans `--confirm`.

Les sorties sont datees :

```text
output/data/2026-09-26-signal-matin.json
output/preview/2026-09-26-signal-matin.html
output/pdf/2026-09-26-signal-matin.pdf
```

## Passer aux vraies donnees

Dans `config.yaml`, remplace `demo: true` par `demo: false`, puis active seulement
les modules utiles :

```yaml
modules:
  weather: true
  calendar: true
  tasks: true
  news: true
  tech: true
  rss: true
  games: true
  tech_vocabulary: true
  recommendations: true
```

Une source absente ne bloque pas l'edition. Sa section reste vide ou disparait ;
aucune fausse information n'est inventee pour la remplacer.

## Meteo

Open-Meteo fonctionne sans cle API :

```yaml
weather:
  location: "Lyon"
  latitude: 45.7640
  longitude: 4.8357
```

## Flux RSS et actualites

Chaque flux choisit son attribution et sa rubrique :

```yaml
news:
  limit: 12
  max_age_hours: 72
  feeds:
    - name: "Nom du media"
      category: "Monde"
      url: "https://media.example/rss.xml"
    - name: "Autre source"
      category: "Culture"
      url: "https://source.example/feed"

tech:
  limit: 6
  feeds:
    - name: "Veille tech"
      category: "Tech"
      url: "https://tech.example/rss.xml"
```

Les titres, résumés, dates, URLs et noms des médias restent associés à chaque
article. Les informations techniques sur les connecteurs ne sont pas imprimées.

## Agenda ICS

Les fichiers locaux et URLs ICS sont acceptes :

```yaml
calendar:
  ics:
    - name: "Agenda personnel"
      source: "calendars/agenda.ics"
    - name: "Calendrier partage"
      source: "https://example.org/private-calendar.ics"
```

Ne place jamais une URL privee dans `config.example.yaml` ou dans un commit.

## Google Calendar

Installe les dependances facultatives :

```bash
pip install -e ".[google]"
```

Dans Google Cloud Console, cree un client OAuth de type application de bureau,
telecharge le JSON sous le nom `credentials.json`, puis configure :

```yaml
calendar:
  google:
    enabled: true
    calendar_id: "primary"
    credentials_file: "credentials.json"
    token_file: "token.json"
```

Connecte le compte une seule fois :

```bash
signal-matin auth-google
```

Le scope est en lecture seule. `credentials.json` et `token.json` sont ignores
par Git.

## Priorites et rappels

```yaml
tasks:
  priorities:
    - title: "Finaliser le dossier principal"
      importance: "high"
    - "Faire le point avant midi"
  reminders:
    - title: "Envoyer le compte rendu"
      due: "2026-09-26T16:00:00+02:00"
      context: "Travail"
```

## Densite et pagination

```bash
signal-matin generate --demo --mode compact
signal-matin generate --demo --mode standard
signal-matin generate --demo --mode extended
```

| Mode | Usage |
|---|---|
| `compact` | Brief rapide, peu de contenu et environ quatre pages. |
| `standard` | Edition quotidienne équilibrée avec dossiers et page ludique. |
| `extended` | Edition riche, davantage de développements et de cahiers. |
| `auto` | Choix automatique d'après la quantité de contenu. |

Une brève importante n'est pas seulement tronquée : les modes standard et
extended créent des pages `En bref, en detail`, avec contexte et points clés.

## Impression

Prépare une impression sans l'envoyer :

```bash
signal-matin print --demo --printer "Nom exact"
```

Envoie-la réellement :

```bash
signal-matin print --live --printer "Nom exact" --duplex --confirm
```

- Windows utilise le pilote selectionne et un rendu raster plein A4.
- macOS et Linux utilisent CUPS (`lp`).
- l'installation et les tests n'impriment jamais.

## Automatisation quotidienne

### Windows Task Scheduler

Generation seule à 8 h :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows_task.ps1 -Time "08:00"
```

Impression recto verso explicite :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows_task.ps1 `
  -Time "08:00" -Print -Duplex -Printer "Nom exact"
```

### cron sous Linux/macOS

Le script affiche la ligne à ajouter sans modifier la crontab :

```bash
sh scripts/install_cron.sh 08:00 generate
sh scripts/install_cron.sh 08:00 print
```

## Architecture

```text
Sources facultatives
  RSS / Open-Meteo / ICS / Google Calendar / YAML
                    |
                    v
          Connectors / Adapters
                    |
                    v
       Normalisation Pydantic stricte
                    |
                    v
          MorningEdition JSON
                    |
                    v
          Regles editoriales
                    |
                    v
       Renderer HTML/CSS autonome
                    |
                    v
      Playwright / Chromium -> PDF A4
                    |
                    v
          Impression facultative
```

Les données et le design sont séparés :

- `src/signal_matin/connectors/` dialogue avec les sources ;
- `models.py` définit le contrat JSON ;
- `pipeline.py` orchestre et hiérarchise ;
- `renderer.py` ne connaît aucune clé ni API ;
- `web/signal_matin.css` contient toute la direction artistique ;
- `pdf.py` vérifie les débordements avant l'export A4 ;
- `printer.py` exige une confirmation explicite.

## Créer un connecteur

1. Ajoute un module dans `src/signal_matin/connectors/`.
2. Retourne des modèles normalisés et un `DataSourceStatus`.
3. Branche-le dans `pipeline.py`, jamais dans le renderer.
4. Ajoute un exemple générique dans `config.example.yaml`.
5. Écris un test avec des données fictives, sans appel réseau réel.

Un connecteur ne doit pas écrire de secret dans le JSON d'édition ni dans les
logs. Les erreurs doivent dégrader seulement leur propre section.

## Personnaliser le design

La feuille `web/signal_matin.css` est optimisée pour `@page { size: A4 }`.
Conserve les marges physiques, les hauteurs de page et les tests de débordement.
Les grandes familles typographiques sont configurées dans les variables CSS.

Pour itérer :

```bash
signal-matin preview --demo --mode standard
pytest tests/test_renderer.py
```

## Tests

```bash
pip install -e ".[dev]"
playwright install chromium
pytest
```

La CI GitHub vérifie : validation des données, sections absentes, génération
HTML, pagination compact/standard/extended, absence de débordement et PDF A4.

## Confidentialite

- aucune clé n'est nécessaire pour le mode démonstration, RSS, météo ou ICS ;
- `.env`, `config.yaml`, OAuth, calendriers et sorties sont ignorés par Git ;
- les URLs privées restent uniquement dans la configuration locale ;
- aucune impression n'est déclenchée pendant l'installation ou les tests ;
- le dépôt ne contient aucune donnée issue d'une installation personnelle.

## FAQ

**Chromium est introuvable**
Lance `playwright install chromium` dans l'environnement Python actif.

**Une page déborde**
Réduis le nombre d'articles du connecteur concerné ou utilise `extended`. Le
moteur refuse volontairement un PDF avec un débordement majeur.

**L'agenda Google est vide**
Vérifie `enabled: true`, puis relance `signal-matin auth-google`.

**Aucune imprimante n'est choisie**
Indique son nom exact avec `--printer`. Signal Matin ne change jamais
l'imprimante par défaut du système.

## Licence

MIT. Voir [LICENSE](LICENSE).

# Installer Signal Matin avec l'aide d'une IA

Ce guide s'adresse aux personnes qui ne sont pas a l'aise avec un terminal. Il
ne remplace pas le programme d'installation guidee : il donne a une IA le bon
contexte pour vous accompagner sans lui transmettre de secret.

## La voie la plus simple

Apres avoir telecharge ou clone le depot, ouvrez un terminal dans son dossier et
lancez :

```bash
python scripts/setup.py
```

Le script cree un environnement isole, installe les dependances et ouvre une
edition fictive. Aucune cle API et aucune imprimante ne sont necessaires.

## Prompt a copier dans votre IA

Copiez le texte ci-dessous dans l'assistant de votre choix :

```text
Je veux installer le projet open source Signal Matin depuis
https://github.com/sosoj92/signal-matin.

Accompagne-moi comme une personne debutante, une seule etape a la fois. Commence
par identifier mon systeme (Windows, macOS ou Linux), verifier Python 3.11+, puis
faire cloner ou telecharger le depot. Utilise d'abord le programme officiel
`python scripts/setup.py`. Si une commande echoue, explique le message en mots
simples et donne seulement la prochaine commande necessaire.

Objectif initial : ouvrir l'edition de demonstration, sans aucune API et sans
impression. Ensuite, fais executer `python scripts/doctor.py`, puis aide-moi a
activer uniquement les sources que je choisis dans config.yaml.

Regles importantes :
- ne me demande jamais de coller une cle API, un token OAuth ou une URL de
  calendrier privee dans le chat ; indique-moi seulement dans quel fichier local
  la placer ;
- ne publie et ne committe jamais config.yaml, .env, credentials.json,
  token.json, un calendrier ICS ou le dossier output ;
- ne lance jamais une impression sans me demander une confirmation explicite ;
- ne modifie pas le code tant que l'installation normale n'a pas ete testee.
```

## Ce que l'IA peut vous demander

- la version affichee par `python --version` ;
- votre systeme d'exploitation ;
- le message d'erreur exact, sans vos cles ni tokens ;
- les rubriques que vous voulez activer ;
- le nom de votre imprimante, uniquement si vous souhaitez imprimer.

## Ce que vous ne devez jamais envoyer

Ne partagez pas le contenu de `.env`, `config.yaml`, `credentials.json`,
`token.json`, une URL ICS privee ou une cle d'API. Ces fichiers sont ignores par
Git, mais ils restent vos donnees personnelles.

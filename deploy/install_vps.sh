#!/usr/bin/env bash
# Déploie Signal Matin sur un VPS Docker + systemd.
# Usage (depuis le Mac, à la racine du projet) :
#   deploy/install_vps.sh root@109.176.197.104 ~/.ssh/id_ed25519_hostinger [--no-test]
# --no-test : met à jour sans lancer d'édition (donc sans impression).
set -euo pipefail
HOST="$1"; KEY="${2:-$HOME/.ssh/id_ed25519}"; TEST_RUN=1
[ "${3:-}" = "--no-test" ] && TEST_RUN=0
SSH=(ssh -i "$KEY" "$HOST")

"${SSH[@]}" 'mkdir -p /opt/signal-matin/app /opt/signal-matin/output /opt/signal-matin/secrets && chmod 700 /opt/signal-matin/secrets'
rsync -az --delete --exclude-from=.dockerignore -e "ssh -i $KEY" ./ "$HOST":/opt/signal-matin/app/

"${SSH[@]}" TEST_RUN=$TEST_RUN bash -s <<'REMOTE'
set -euo pipefail
cd /opt/signal-matin
# Config de démo au premier déploiement seulement ; jamais écrasée ensuite.
[ -f config.yaml ] || cp app/config.example.yaml config.yaml
[ -f .env ] || { touch .env; chmod 600 .env; }
docker build -t signal-matin:latest app
# Conteneur témoin, jamais démarré : l'image reste « utilisée » et échappe aux
# nettoyages « docker image prune -a » programmés sur le serveur.
docker rm -f signal-matin-keep >/dev/null 2>&1 || true
docker create --name signal-matin-keep signal-matin:latest >/dev/null
install -m 644 app/deploy/systemd/signal-matin.service /etc/systemd/system/
install -m 644 app/deploy/systemd/signal-matin.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now signal-matin.timer
if [ "$TEST_RUN" = 1 ]; then
  systemctl start signal-matin.service   # génération de test immédiate
  ls -la output/pdf
fi
systemctl list-timers signal-matin.timer --no-pager
REMOTE

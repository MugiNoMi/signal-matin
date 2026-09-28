#!/usr/bin/env bash
# Déploie Signal Matin sur un VPS Docker + systemd.
# Usage (depuis le Mac, à la racine du projet) :
#   deploy/install_vps.sh root@109.176.197.104 ~/.ssh/id_ed25519_hostinger
set -euo pipefail
HOST="$1"; KEY="${2:-$HOME/.ssh/id_ed25519}"
SSH=(ssh -i "$KEY" "$HOST")

"${SSH[@]}" 'mkdir -p /opt/signal-matin/app /opt/signal-matin/output'
rsync -az --delete --exclude-from=.dockerignore -e "ssh -i $KEY" ./ "$HOST":/opt/signal-matin/app/

"${SSH[@]}" bash -s <<'REMOTE'
set -euo pipefail
cd /opt/signal-matin
# Config de démo au premier déploiement seulement ; jamais écrasée ensuite.
[ -f config.yaml ] || cp app/config.example.yaml config.yaml
[ -f .env ] || { touch .env; chmod 600 .env; }
docker build -t signal-matin:latest app
install -m 644 app/deploy/systemd/signal-matin.service /etc/systemd/system/
install -m 644 app/deploy/systemd/signal-matin.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now signal-matin.timer
systemctl start signal-matin.service   # génération de test immédiate
ls -la output/pdf
systemctl list-timers signal-matin.timer --no-pager
REMOTE

#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}
TIME=${1:-08:00}
MODE=${2:-generate}
HOUR=${TIME%:*}
MINUTE=${TIME#*:}

case "$MODE" in
  generate) COMMAND="$PYTHON $ROOT/main.py --generate --live" ;;
  print) COMMAND="$PYTHON $ROOT/main.py --print --live --confirm" ;;
  *) echo "Usage: $0 HH:MM [generate|print]" >&2; exit 2 ;;
esac

LINE="$MINUTE $HOUR * * * cd $ROOT && $COMMAND"
echo "Ligne cron proposee:"
echo "$LINE"
echo ""
echo "Aucune modification n'a ete faite. Ajoute cette ligne avec: crontab -e"

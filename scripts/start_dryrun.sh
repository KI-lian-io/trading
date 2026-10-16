#!/bin/zsh
# Start the dry-run bot detached: survives closed terminals and app restarts,
# and keeps the Mac from idle-sleeping while it runs. Stop with scripts/stop_dryrun.sh.
set -e
cd "${0:A:h}/.."
mkdir -p user_data/logs
PIDFILE=user_data/logs/dryrun.pid

if [[ -f $PIDFILE ]] && kill -0 "$(cat $PIDFILE)" 2>/dev/null; then
  echo "dry-run bot already running (PID $(cat $PIDFILE))"
  exit 0
fi

set -a; . ./.env; set +a
nohup caffeinate -i .venv/bin/freqtrade trade -c user_data/config_dryrun.json \
  --logfile user_data/logs/dryrun.log > user_data/logs/dryrun.stdout 2>&1 &
echo $! > $PIDFILE
echo "dry-run bot started (PID $(cat $PIDFILE)), log: user_data/logs/dryrun.log"

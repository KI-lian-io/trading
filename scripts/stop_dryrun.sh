#!/bin/zsh
# Stop the dry-run bot started by scripts/start_dryrun.sh.
cd "${0:A:h}/.."
PIDFILE=user_data/logs/dryrun.pid

if [[ -f $PIDFILE ]] && kill -0 "$(cat $PIDFILE)" 2>/dev/null; then
  # The PID is freqtrade itself; caffeinate runs as its child. SIGTERM lets freqtrade shut down cleanly.
  pkill -TERM -P "$(cat $PIDFILE)"
  kill "$(cat $PIDFILE)" 2>/dev/null
  rm -f $PIDFILE
  echo "dry-run bot stopped"
else
  echo "dry-run bot not running"
fi

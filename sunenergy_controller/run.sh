#!/usr/bin/env bash
echo "Starting SunEnergy XT Controller..."

python3 /app/controller.py &
PID_CTRL=$!

python3 /app/web_ui.py &
PID_UI=$!

# Beenden, sobald EINER der beiden Prozesse stirbt, damit der HA-Supervisor
# den Container neu startet (statt mit totem Controller "gesund" weiterzulaufen).
wait -n
echo "Ein Prozess wurde beendet — fahre Container herunter, damit ein Neustart erfolgt."
kill "$PID_CTRL" "$PID_UI" 2>/dev/null
exit 1

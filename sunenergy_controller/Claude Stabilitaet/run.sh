#!/usr/bin/env bash
echo "Starting SunEnergy XT Controller..."

python3 /app/controller.py &
PID_CTRL=$!

python3 /app/web_ui.py &
PID_UI=$!

# v1.9.2: SIGTERM/SIGINT abfangen und an die Python-Prozesse weiterleiten.
# Ohne trap leitet bash (PID 1) das Signal NICHT an Hintergrundjobs weiter —
# der Controller würde nach Timeout per SIGKILL sterben, ohne den Safe-State
# (MM=1) setzen zu können.
term_handler() {
  echo "Stop-Signal empfangen — beende Prozesse sauber..."
  kill -TERM "$PID_CTRL" "$PID_UI" 2>/dev/null
  wait
  echo "Sauber beendet."
  exit 0
}
trap term_handler TERM INT

# Beenden, sobald EINER der beiden Prozesse stirbt, damit der HA-Supervisor
# den Container neu startet (statt mit totem Controller "gesund" weiterzulaufen).
wait -n
echo "Ein Prozess wurde beendet — fahre Container herunter, damit ein Neustart erfolgt."
kill "$PID_CTRL" "$PID_UI" 2>/dev/null
exit 1

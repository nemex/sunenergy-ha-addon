#!/usr/bin/with-contenv bashio

bashio::log.info "Starting SunEnergy XT Controller..."

# Start controller
python3 /app/controller.py &

# Start Web UI
python3 /app/web_ui.py

wait

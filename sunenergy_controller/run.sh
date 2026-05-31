#!/bin/sh
echo "Starting SunEnergy XT Controller..."
python3 /app/controller.py &
python3 /app/web_ui.py &
wait

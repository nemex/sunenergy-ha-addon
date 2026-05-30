#!/usr/bin/env python3
"""
SunEnergy XT Controller — Web UI
Einfaches Live-Dashboard auf Port 8765
"""

import json
import time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

STATE_PATH = "/data/controller_state.json"

HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="5">
<title>SunEnergy XT Controller</title>
<style>
  :root {
    --bg: #0a0e14; --surface: #111822; --border: #1e2d3d;
    --accent: #f0a500; --green: #00e676; --red: #ff3d57;
    --blue: #00c2ff; --text: #cdd9e5; --muted: #4a5568;
    --mono: 'Courier New', monospace;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: sans-serif;
         padding: 24px; min-height: 100vh; }
  h1 { color: var(--accent); font-size: 18px; letter-spacing: 2px;
       text-transform: uppercase; margin-bottom: 24px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 16px; margin-bottom: 24px; }
  .card { background: var(--surface); border: 1px solid var(--border);
          border-radius: 4px; padding: 16px; }
  .card-title { font-size: 10px; color: var(--muted); letter-spacing: 2px;
                text-transform: uppercase; margin-bottom: 8px; }
  .card-value { font-family: var(--mono); font-size: 28px; color: var(--blue); }
  .card-value.positive { color: var(--green); }
  .card-value.negative { color: var(--red); }
  .card-value.warning { color: var(--accent); }
  .mode { display: inline-block; padding: 4px 12px; border-radius: 3px;
          font-size: 12px; font-family: var(--mono); letter-spacing: 1px; }
  .mode.active { background: rgba(0,230,118,0.15); color: var(--green);
                 border: 1px solid var(--green); }
  .mode.night { background: rgba(74,85,104,0.3); color: var(--muted);
                border: 1px solid var(--muted); }
  .mode.calibration { background: rgba(240,165,0,0.15); color: var(--accent);
                      border: 1px solid var(--accent); }
  .footer { color: var(--muted); font-size: 11px; margin-top: 24px; }
  .soc-bar { height: 6px; background: var(--border); border-radius: 3px;
             margin-top: 8px; overflow: hidden; }
  .soc-fill { height: 100%; background: var(--green); border-radius: 3px; }
</style>
</head>
<body>
<h1>⚡ SunEnergy XT Controller</h1>
<div class="grid">
  <div class="card">
    <div class="card-title">Modus</div>
    <div class="mode {mode_class}">{mode_label}</div>
  </div>
  <div class="card">
    <div class="card-title">GS Sollwert</div>
    <div class="card-value {gs_class}">{gs_value} W</div>
  </div>
  <div class="card">
    <div class="card-title">Netz (gefiltert)</div>
    <div class="card-value {grid_class}">{grid_value} W</div>
  </div>
  <div class="card">
    <div class="card-title">PI Integral</div>
    <div class="card-value">{integral}</div>
  </div>
  <div class="card">
    <div class="card-title">SOC</div>
    <div class="card-value">{soc}%</div>
    <div class="soc-bar"><div class="soc-fill" style="width:{soc}%"></div></div>
  </div>
  <div class="card">
    <div class="card-title">Tage seit Vollladung</div>
    <div class="card-value {calib_class}">{calib_days}</div>
  </div>
</div>
<div class="footer">Letzte Aktualisierung: {timestamp} · Automatische Aktualisierung alle 5s</div>
</body>
</html>"""


def load_state() -> dict:
    try:
        if Path(STATE_PATH).exists():
            with open(STATE_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


class UIHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Kein HTTP-Logging

    def do_GET(self):
        if self.path == "/":
            state = load_state()

            mode = state.get("active_mode", "unknown")
            mode_class = mode if mode in ("active", "night", "calibration") else "night"
            mode_labels = {
                "active": "AKTIV REGELND",
                "night": "NACHT / STANDBY",
                "calibration": "ZWANGSLADUNG",
            }
            mode_label = mode_labels.get(mode, mode.upper())

            gs = state.get("last_gs", 0)
            grid = state.get("grid_p_filtered", 0)
            integral = round(state.get("pi_integral", 0), 2)

            calib_ts = state.get("last_calibration_ts", 0)
            calib_days = round((time.time() - calib_ts) / 86400, 1) if calib_ts else "—"
            calib_class = "warning" if isinstance(calib_days, float) and calib_days > 12 else ""

            html = HTML.format(
                mode_class=mode_class,
                mode_label=mode_label,
                gs_value=int(gs),
                gs_class="negative" if gs < 0 else "positive" if gs > 0 else "",
                grid_value=round(grid, 1),
                grid_class="negative" if grid > 50 else "positive" if grid < -30 else "",
                integral=integral,
                soc=round(state.get("soc", 0)),
                calib_days=calib_days,
                calib_class=calib_class,
                timestamp=time.strftime("%H:%M:%S"),
            )

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())

        elif self.path == "/state":
            state = load_state()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(state).encode())

        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8765), UIHandler)
    print("Web UI läuft auf http://0.0.0.0:8765")
    server.serve_forever()

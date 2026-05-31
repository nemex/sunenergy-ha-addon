#!/usr/bin/env python3
"""
SunEnergy XT Controller — Web UI + Meter Proxy
Port 8765:
  GET /        → Live Dashboard mit Chart
  GET /state   → JSON State
  GET /meter   → Shelly Pro 3EM Proxy
  GET /log     → CSV Log Download
  GET /api     → JSON für Chart (letzte 100 Datenpunkte)
"""

import csv
import json
import os
import time
import requests
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

STATE_PATH = "/data/controller_state.json"
OPTIONS_PATH = "/data/options.json"
CSV_PATH = "/data/controller_log.csv"

def load_state() -> dict:
    try:
        if Path(STATE_PATH).exists():
            with open(STATE_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def load_options() -> dict:
    try:
        if Path(OPTIONS_PATH).exists():
            with open(OPTIONS_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def get_shelly_power(shelly_ip: str) -> float:
    try:
        r = requests.get(f"http://{shelly_ip}/rpc/EM.GetStatus?id=0", timeout=3)
        if r.status_code == 200:
            return float(r.json().get("total_act_power", 0))
    except Exception:
        pass
    return 0.0

def get_csv_data(n=100) -> list:
    """Liest die letzten n Zeilen aus der CSV."""
    try:
        if not os.path.exists(CSV_PATH):
            return []
        with open(CSV_PATH, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        return rows[-n:]
    except Exception:
        return []

HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SunEnergy XT Controller</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #0a0e14; --surface: #111822; --border: #1e2d3d;
    --accent: #f0a500; --green: #00e676; --red: #ff3d57;
    --blue: #00c2ff; --text: #cdd9e5; --muted: #4a5568;
    --mono: 'Courier New', monospace;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: sans-serif; padding: 20px; }
  h1 { color: var(--accent); font-size: 16px; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 20px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 4px; padding: 14px; }
  .card-title { font-size: 10px; color: var(--muted); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 6px; }
  .card-value { font-family: var(--mono); font-size: 24px; color: var(--blue); }
  .card-value.pos { color: var(--green); }
  .card-value.neg { color: var(--red); }
  .card-value.warn { color: var(--accent); }
  .mode { display: inline-block; padding: 3px 10px; border-radius: 3px; font-size: 11px; font-family: var(--mono); }
  .mode.active { background: rgba(0,230,118,0.15); color: var(--green); border: 1px solid var(--green); }
  .mode.soc_full { background: rgba(240,165,0,0.15); color: var(--accent); border: 1px solid var(--accent); }
  .mode.night { background: rgba(74,85,104,0.3); color: var(--muted); border: 1px solid var(--muted); }
  .soc-bar { height: 5px; background: var(--border); border-radius: 3px; margin-top: 6px; overflow: hidden; }
  .soc-fill { height: 100%; background: var(--green); border-radius: 3px; transition: width 1s; }
  .chart-wrap { background: var(--surface); border: 1px solid var(--border); border-radius: 4px; padding: 16px; margin-bottom: 20px; }
  .chart-wrap h2 { font-size: 11px; color: var(--muted); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 12px; }
  canvas { max-height: 220px; }
  .footer { color: var(--muted); font-size: 11px; margin-top: 16px; display: flex; justify-content: space-between; }
  .btn { background: var(--surface); border: 1px solid var(--border); color: var(--accent); 
         font-family: var(--mono); font-size: 11px; padding: 6px 12px; border-radius: 3px; 
         cursor: pointer; text-decoration: none; }
  .btn:hover { border-color: var(--accent); }
</style>
</head>
<body>
<h1>⚡ SunEnergy XT Controller</h1>

<div class="grid" id="cards">
  <div class="card"><div class="card-title">Modus</div><div id="c-mode" class="mode night">—</div></div>
  <div class="card"><div class="card-title">Netz</div><div id="c-grid" class="card-value">— W</div></div>
  <div class="card"><div class="card-title">Haus</div><div id="c-haus" class="card-value">— W</div></div>
  <div class="card"><div class="card-title">Solar (HMS)</div><div id="c-solar" class="card-value">— W</div></div>
  <div class="card"><div class="card-title">GS Sollwert</div><div id="c-gs" class="card-value">— W</div></div>
  <div class="card"><div class="card-title">IS Limit</div><div id="c-is" class="card-value">— W</div></div>
  <div class="card"><div class="card-title">HMS Limit</div><div id="c-hms" class="card-value">— W</div></div>
  <div class="card">
    <div class="card-title">SOC</div>
    <div id="c-soc" class="card-value">— %</div>
    <div class="soc-bar"><div id="c-soc-bar" class="soc-fill" style="width:0%"></div></div>
  </div>
</div>

<div class="chart-wrap">
  <h2>Netzleistung (letzte 100 Messwerte)</h2>
  <canvas id="chart-grid"></canvas>
</div>

<div class="chart-wrap">
  <h2>Solar / Haus / IS / HMS-Limit</h2>
  <canvas id="chart-power"></canvas>
</div>

<div class="footer">
  <span id="ts">—</span>
  <a href="/log" class="btn">⬇ CSV Download</a>
</div>

<script>
const chartColors = {
  grid: '#ff3d57', haus: '#00c2ff', solar: '#f0a500',
  is: '#00e676', hms: '#7c3aed', gs: '#ec4899'
};

function makeChart(id, datasets, yLabel) {
  return new Chart(document.getElementById(id), {
    type: 'line',
    data: { labels: [], datasets },
    options: {
      responsive: true,
      animation: false,
      plugins: { legend: { labels: { color: '#cdd9e5', font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: '#4a5568', maxTicksLimit: 8, font: { size: 10 } }, grid: { color: '#1e2d3d' } },
        y: { ticks: { color: '#4a5568', font: { size: 10 } }, grid: { color: '#1e2d3d' }, title: { display: true, text: yLabel, color: '#4a5568', font: { size: 10 } } }
      }
    }
  });
}

const gridChart = makeChart('chart-grid', [
  { label: 'Netz (W)', data: [], borderColor: chartColors.grid, backgroundColor: 'rgba(255,61,87,0.1)', tension: 0.3, pointRadius: 0, fill: true }
], 'Watt');

const powerChart = makeChart('chart-power', [
  { label: 'Solar HMS (W)', data: [], borderColor: chartColors.solar, tension: 0.3, pointRadius: 0 },
  { label: 'Haus (W)', data: [], borderColor: chartColors.haus, tension: 0.3, pointRadius: 0 },
  { label: 'IS Limit (W)', data: [], borderColor: chartColors.is, tension: 0.3, pointRadius: 0, borderDash: [4,2] },
  { label: 'HMS Limit (W)', data: [], borderColor: chartColors.hms, tension: 0.3, pointRadius: 0, borderDash: [4,2] },
], 'Watt');

function updateCards(state, csv) {
  const mode = state.active_mode || 'night';
  const el = document.getElementById('c-mode');
  el.textContent = { active: 'AKTIV REGELND', soc_full: 'SOC VOLL (IS)', night: 'NACHT', calibration: 'ZWANGSLADUNG' }[mode] || mode.toUpperCase();
  el.className = 'mode ' + mode;

  const grid = parseFloat(csv.grid_p || 0);
  setCard('c-grid', grid.toFixed(0) + ' W', grid > 50 ? 'neg' : grid < -30 ? 'pos' : '');
  setCard('c-haus', parseFloat(csv.haus_p || 0).toFixed(0) + ' W', '');
  setCard('c-solar', parseFloat(csv.solar_p || 0).toFixed(0) + ' W', 'pos');
  setCard('c-gs', parseFloat(csv.gs || 0).toFixed(0) + ' W', '');
  setCard('c-is', csv.is_target !== undefined ? parseFloat(csv.is_target).toFixed(0) + ' W' : '— W', '');
  setCard('c-hms', csv.hms_limit !== undefined ? parseFloat(csv.hms_limit).toFixed(0) + ' W' : '— W', '');

  const soc = parseFloat(csv.soc || state.soc || 0);
  setCard('c-soc', soc.toFixed(0) + ' %', soc < 20 ? 'warn' : '');
  document.getElementById('c-soc-bar').style.width = Math.min(100, soc) + '%';
  document.getElementById('ts').textContent = 'Letzte Aktualisierung: ' + new Date().toLocaleTimeString('de-DE');
}

function setCard(id, text, cls) {
  const el = document.getElementById(id);
  el.textContent = text;
  el.className = 'card-value' + (cls ? ' ' + cls : '');
}

function updateCharts(rows) {
  const labels = rows.map(r => r.ts ? r.ts.split(' ')[1].substring(0,5) : '');
  
  gridChart.data.labels = labels;
  gridChart.data.datasets[0].data = rows.map(r => parseFloat(r.grid_p || 0));
  gridChart.update();

  powerChart.data.labels = labels;
  powerChart.data.datasets[0].data = rows.map(r => parseFloat(r.solar_p || 0));
  powerChart.data.datasets[1].data = rows.map(r => parseFloat(r.haus_p || 0));
  powerChart.data.datasets[2].data = rows.map(r => parseFloat(r.is_target || 0));
  powerChart.data.datasets[3].data = rows.map(r => parseFloat(r.hms_limit || 0));
  powerChart.update();
}

async function refresh() {
  try {
    const [stateR, apiR] = await Promise.all([
      fetch('/state').then(r => r.json()),
      fetch('/api').then(r => r.json())
    ]);
    if (apiR.rows && apiR.rows.length > 0) {
      updateCards(stateR, apiR.rows[apiR.rows.length - 1]);
      updateCharts(apiR.rows);
    }
  } catch(e) {}
}

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>"""


class UIHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        opts = load_options()
        shelly_ip = opts.get("shelly_ip", "192.168.178.98")

        if self.path == "/meter":
            power = get_shelly_power(shelly_ip)
            meter_data = {
                "id": 0,
                "total_act_power": round(power, 1),
                "total_current": 0.0,
                "total_aprt_power": round(abs(power), 1),
                "a_act_power": round(power / 3, 1),
                "b_act_power": round(power / 3, 1),
                "c_act_power": round(power / 3, 1),
                "a_current": 0.0, "b_current": 0.0, "c_current": 0.0,
                "a_voltage": 230.0, "b_voltage": 230.0, "c_voltage": 230.0,
                "a_freq": 50.0, "b_freq": 50.0, "c_freq": 50.0,
            }
            self._json(meter_data)

        elif self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode())

        elif self.path == "/state":
            self._json(load_state())

        elif self.path == "/api":
            rows = get_csv_data(100)
            self._json({"rows": rows})

        elif self.path == "/log":
            if os.path.exists(CSV_PATH):
                with open(CSV_PATH, "r") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv")
                self.send_header("Content-Disposition", "attachment; filename=controller_log.csv")
                self.end_headers()
                self.wfile.write(data.encode())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Noch keine Logdaten")
        else:
            self.send_response(404)
            self.end_headers()

    def _json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8765), UIHandler)
    print("Web UI läuft auf http://0.0.0.0:8765")
    server.serve_forever()

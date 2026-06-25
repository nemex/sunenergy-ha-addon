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
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

STATE_PATH = "/data/controller_state.json"
PROXY_STATE_PATH = "/data/proxy_state.json"
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

def load_proxy_state() -> dict:
    try:
        if Path(PROXY_STATE_PATH).exists():
            with open(PROXY_STATE_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_proxy_state(updates: dict):
    try:
        st = load_proxy_state()
        st.update(updates)
        temp_path = PROXY_STATE_PATH + ".tmp"
        with open(temp_path, "w") as f:
            json.dump(st, f)
        os.replace(temp_path, PROXY_STATE_PATH)
    except Exception:
        pass

def load_options() -> dict:
    try:
        if Path(OPTIONS_PATH).exists():
            with open(OPTIONS_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

_SHELLY_CACHE = {"time": 0.0, "value": 0.0}

def get_shelly_power(shelly_ip: str) -> float:
    now = time.time()
    if now - _SHELLY_CACHE["time"] < 0.5:
        return _SHELLY_CACHE["value"]
    try:
        r = requests.get(f"http://{shelly_ip}/rpc/EM.GetStatus?id=0", timeout=2)
        if r.status_code == 200:
            val = float(r.json().get("total_act_power", 0))
            _SHELLY_CACHE["time"] = now
            _SHELLY_CACHE["value"] = val
            return val
    except Exception:
        pass
    return _SHELLY_CACHE["value"]

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
  .mode.feed_in { background: rgba(0,194,255,0.15); color: var(--blue); border: 1px solid var(--blue); }
  .mode.feed_in_standby { background: rgba(240,165,0,0.15); color: var(--accent); border: 1px solid var(--accent); }
  .mode.bypass { background: rgba(236,72,153,0.15); color: #ec4899; border: 1px solid #ec4899; }
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
  <div class="card" id="card-gs-l2" style="display:none"><div class="card-title">GS Sollwert L2</div><div id="c-gs-l2" class="card-value">— W</div></div>
  <div class="card"><div class="card-title">IS Limit</div><div id="c-is" class="card-value">— W</div></div>
  <div class="card" id="card-is-l2" style="display:none"><div class="card-title">IS Limit L2</div><div id="c-is-l2" class="card-value">— W</div></div>
  <div class="card"><div class="card-title">HMS 2000 Limit</div><div id="c-hms-2000" class="card-value">— W</div></div>
  <div class="card"><div class="card-title">HMS 1600 Limit</div><div id="c-hms-1600" class="card-value">— W</div></div>
  <div class="card">
    <div class="card-title">SOC</div>
    <div id="c-soc" class="card-value">— %</div>
    <div class="soc-bar"><div id="c-soc-bar" class="soc-fill" style="width:0%"></div></div>
  </div>
  <div class="card" id="card-soc-l2" style="display:none">
    <div class="card-title">SOC L2</div>
    <div id="c-soc-l2" class="card-value">— %</div>
    <div class="soc-bar"><div id="c-soc-bar-l2" class="soc-fill" style="width:0%"></div></div>
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
 
<div class="chart-wrap">
  <h2>Wechselrichter — Ist vs. Limit</h2>
  <div style="margin-bottom:10px">
    <span style="font-size:10px;color:#4a5568">Status: </span>
    <span id="inv-status" style="font-size:11px;font-family:monospace">—</span>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:16px;margin-bottom:8px" id="inv-grid">
    <div>
      <div id="inv-se-title" style="font-size:10px;color:#4a5568;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px">SunEnergyXT (DC+AC)</div>
      <div style="display:flex;justify-content:space-between;margin-bottom:2px">
        <span style="font-size:11px;color:#cdd9e5">Ist: <span id="inv-se-ist">—</span> W</span>
        <span style="font-size:11px;color:#4a5568">IS Limit: <span id="inv-se-lim">—</span> W</span>
      </div>
      <div style="height:8px;background:#1e2d3d;border-radius:4px;overflow:hidden;margin-bottom:4px">
        <div id="inv-se-bar" style="height:100%;background:#00e676;border-radius:4px;width:0%;transition:width 1s"></div>
      </div>
      <div id="inv-se-reason" style="font-size:10px;color:#4a5568">—</div>
    </div>
    <div id="inv-se-l2-wrap" style="display:none">
      <div style="font-size:10px;color:#4a5568;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px">SunEnergyXT L2</div>
      <div style="display:flex;justify-content:space-between;margin-bottom:2px">
        <span style="font-size:11px;color:#cdd9e5">Ist: <span id="inv-se-l2-ist">—</span> W</span>
        <span style="font-size:11px;color:#4a5568">IS Limit: <span id="inv-se-l2-lim">—</span> W</span>
      </div>
      <div style="height:8px;background:#1e2d3d;border-radius:4px;overflow:hidden;margin-bottom:4px">
        <div id="inv-se-l2-bar" style="height:100%;background:#00e676;border-radius:4px;width:0%;transition:width 1s"></div>
      </div>
      <div id="inv-se-l2-reason" style="font-size:10px;color:#4a5568">—</div>
    </div>
    <div>
      <div style="font-size:10px;color:#4a5568;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px">HMS-2000</div>
      <div style="display:flex;justify-content:space-between;margin-bottom:2px">
        <span style="font-size:11px;color:#cdd9e5">Ist: <span id="inv-2000-ist">—</span> W</span>
        <span style="font-size:11px;color:#4a5568">Limit: <span id="inv-2000-lim">—</span> W</span>
      </div>
      <div style="height:8px;background:#1e2d3d;border-radius:4px;overflow:hidden;margin-bottom:4px">
        <div id="inv-2000-bar" style="height:100%;background:#f0a500;border-radius:4px;width:0%;transition:width 1s"></div>
      </div>
      <div id="inv-2000-reason" style="font-size:10px;color:#4a5568">—</div>
    </div>
    <div>
      <div style="font-size:10px;color:#4a5568;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px">HMS-1600</div>
      <div style="display:flex;justify-content:space-between;margin-bottom:2px">
        <span style="font-size:11px;color:#cdd9e5">Ist: <span id="inv-1600-ist">—</span> W</span>
        <span style="font-size:11px;color:#4a5568">Limit: <span id="inv-1600-lim">—</span> W</span>
      </div>
      <div style="height:8px;background:#1e2d3d;border-radius:4px;overflow:hidden;margin-bottom:4px">
        <div id="inv-1600-bar" style="height:100%;background:#00c2ff;border-radius:4px;width:0%;transition:width 1s"></div>
      </div>
      <div id="inv-1600-reason" style="font-size:10px;color:#4a5568">—</div>
    </div>
  </div>
</div>
 
<div class="footer">
  <span id="ts">—</span>
  <div>
    <a href="analyse" class="btn" style="border-color:var(--green);color:var(--green)">📊 Systemanalyse</a>
    <a href="log" class="btn" style="margin-left:8px">⬇ CSV Download</a>
    <button class="btn" style="margin-left:8px;border-color:#ff3d57;color:#ff3d57" onclick="deleteLog()">🗑 Log löschen</button>
  </div>
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
  let mode = state.active_mode || 'night';
  // soc_full: wenn aktiv geregelt UND Akku voll (>= soc_normal_max), zeige "SOC VOLL"
  const socNow = parseFloat(csv.soc !== undefined ? csv.soc : (state.soc || 0));
  const socMax = parseFloat(state.soc_normal_max || 95);
  if (mode === 'active' && socNow >= socMax) {
    mode = 'soc_full';
  }
  const el = document.getElementById('c-mode');
  el.textContent = { active: 'AKTIV REGELND', soc_full: 'SOC VOLL (IS)', night: 'NACHT', calibration: 'ZWANGSLADUNG', feed_in: 'EINSPEISUNG AKTIV', feed_in_standby: 'EINSPEISUNG STANDBY', bypass: 'BYPASS AKTIV' }[mode] || mode.toUpperCase();
  el.className = 'mode ' + mode;
 
  const grid = parseFloat(csv.grid_p || state.grid_p_filtered || 0);
  setCard('c-grid', grid.toFixed(0) + ' W', grid > 50 ? 'neg' : grid < -30 ? 'pos' : '');
  setCard('c-haus', parseFloat(csv.haus_p || state.haus_p_last || 0).toFixed(0) + ' W', '');
  setCard('c-solar', parseFloat(csv.solar_p || state.solar_p_last || 0).toFixed(0) + ' W', 'pos');
  
  if (state.has_l2) {
    document.getElementById('card-gs-l2').style.display = 'block';
    document.getElementById('card-is-l2').style.display = 'block';
    document.getElementById('card-soc-l2').style.display = 'block';
    document.getElementById('inv-se-l2-wrap').style.display = 'block';
    
    // Titel L1 Karten anpassen
    document.querySelector('#cards .card:nth-child(5) .card-title').textContent = 'GS Sollwert L1';
    document.querySelector('#cards .card:nth-child(7) .card-title').textContent = 'IS Limit L1';
    document.querySelector('#cards .card:nth-child(11) .card-title').textContent = 'SOC L1';
    document.getElementById('inv-se-title').textContent = 'SunEnergyXT L1';

    // GS L1 und L2
    const gsL1 = parseFloat(csv.gs_l1 !== undefined ? csv.gs_l1 : (state.last_device_gs || 0));
    const gsL2 = parseFloat(csv.gs_l2 !== undefined ? csv.gs_l2 : (state.last_device_gs_l2 || 0));
    setCard('c-gs', gsL1.toFixed(0) + ' W', '');
    setCard('c-gs-l2', gsL2.toFixed(0) + ' W', '');

    // IS L1 und L2
    const isL1 = parseFloat(csv.is_target !== undefined ? csv.is_target : (state.last_device_is || state.last_is || 2400));
    const isL2 = parseFloat(state.last_device_is_l2 || state.last_is_l2 || 2400);
    setCard('c-is', isL1.toFixed(0) + ' W', '');
    setCard('c-is-l2', isL2.toFixed(0) + ' W', '');

    // SOC L1 und L2
    const socL1 = parseFloat(csv.soc !== undefined ? csv.soc : (state.soc || 0));
    const socL2 = parseFloat(csv.soc_l2 !== undefined ? csv.soc_l2 : (state.soc_l2 || 0));
    setCard('c-soc', socL1.toFixed(0) + ' %', socL1 < 20 ? 'warn' : '');
    document.getElementById('c-soc-bar').style.width = Math.min(100, socL1) + '%';
    setCard('c-soc-l2', socL2.toFixed(0) + ' %', socL2 < 20 ? 'warn' : '');
    document.getElementById('c-soc-bar-l2').style.width = Math.min(100, socL2) + '%';
  } else {
    document.getElementById('card-gs-l2').style.display = 'none';
    document.getElementById('card-is-l2').style.display = 'none';
    document.getElementById('card-soc-l2').style.display = 'none';
    document.getElementById('inv-se-l2-wrap').style.display = 'none';
    
    document.querySelector('#cards .card:nth-child(5) .card-title').textContent = 'GS Sollwert';
    document.querySelector('#cards .card:nth-child(7) .card-title').textContent = 'IS Limit';
    document.querySelector('#cards .card:nth-child(11) .card-title').textContent = 'SOC';
    document.getElementById('inv-se-title').textContent = 'SunEnergyXT (DC+AC)';

    setCard('c-gs', parseFloat(csv.gs || state.last_gs || 0).toFixed(0) + ' W', '');
    setCard('c-is', (csv.is_target !== undefined ? parseFloat(csv.is_target) : parseFloat(state.last_is || 0)).toFixed(0) + ' W', '');
    const soc = parseFloat(csv.soc || state.soc || 0);
    setCard('c-soc', soc.toFixed(0) + ' %', soc < 20 ? 'warn' : '');
    document.getElementById('c-soc-bar').style.width = Math.min(100, soc) + '%';
  }
 
  const lim2000 = parseFloat(csv.hms_2000_lim !== undefined ? csv.hms_2000_lim : (state.last_hms_2000_lim !== undefined ? state.last_hms_2000_lim : 2000));
  const lim1600 = parseFloat(csv.hms_1600_lim !== undefined ? csv.hms_1600_lim : (state.last_hms_1600_lim !== undefined ? state.last_hms_1600_lim : 1600));
  setCard('c-hms-2000', lim2000.toFixed(0) + ' W', '');
  setCard('c-hms-1600', lim1600.toFixed(0) + ' W', '');
 
  document.getElementById('ts').textContent = 'Letzte Aktualisierung: ' + new Date().toLocaleTimeString('de-DE');
 
  // Wechselrichter Ist vs Limit
  const seIst  = parseFloat(csv.pv !== undefined ? csv.pv : (state.pv_last || 0));  // L1
  const seLim  = parseFloat(csv.is_target !== undefined ? csv.is_target : (state.last_device_is || state.last_is || 2400));
  
  const seIstL2 = parseFloat(csv.pv_l2 !== undefined ? csv.pv_l2 : (state.pv_last_l2 || 0)); // L2
  const seLimL2 = parseFloat(state.last_device_is_l2 || state.last_is_l2 || 2400);
 
  const h2000Ist = parseFloat(csv.hms_2000 || 0);
  const h1600Ist = parseFloat(csv.hms_1600 || 0);
 
  // Status bestimmen
  const currentGrid = csv.grid_p !== undefined ? parseFloat(csv.grid_p) : grid;
  const currentMode = csv.mode || mode;
  let statusText = '—';
  let seReason = '—', seReasonL2 = '—', h2000Reason = '—', h1600Reason = '—';
 
  if (currentMode === 'night') {
    statusText = '⚪ Nacht — kein Betrieb';
    seReason = 'Nacht';
    seReasonL2 = 'Nacht';
    h2000Reason = 'Nacht';
    h1600Reason = 'Nacht';
  } else if (currentMode === 'bypass') {
    statusText = '🟢 Bypass aktiv — ungedrosselt (' + Math.round(currentGrid) + 'W Einspeisung)';
    seReason = '✅ Bypass (100%)';
    seReasonL2 = '✅ Bypass (100%)';
    h2000Reason = '✅ Bypass (100%)';
    h1600Reason = '✅ Bypass (100%)';
  } else if (currentGrid < -25) {
    statusText = '🟡 Gedrosselt — Überschuss (' + Math.round(currentGrid) + 'W Einspeisung)';
    seReason = seLim < 2400 ? '⬇ gedrosselt (Überschuss)' : '✅ volle Leistung';
    seReasonL2 = seLimL2 < 2400 ? '⬇ gedrosselt (Überschuss)' : '✅ volle Leistung';
    h2000Reason = lim2000 < 2000 ? '⬇ gedrosselt (Überschuss)' : '✅ volle Leistung';
    h1600Reason = lim1600 < 1600 ? '⬇ gedrosselt (Überschuss)' : '✅ volle Leistung';
  } else if (currentGrid > 25) {
    statusText = '🟢 Volle Leistung — Netzbezug (' + Math.round(currentGrid) + 'W)';
    seReason = '✅ volle Leistung';
    seReasonL2 = '✅ volle Leistung';
    h2000Reason = '✅ volle Leistung';
    h1600Reason = '✅ volle Leistung';
  } else {
    statusText = '🟢 Nulleinspeisung aktiv (' + Math.round(currentGrid) + 'W)';
    seReason = seLim < 2400 ? '⬇ leicht gedrosselt' : '✅ volle Leistung';
    seReasonL2 = seLimL2 < 2400 ? '⬇ leicht gedrosselt' : '✅ volle Leistung';
    h2000Reason = lim2000 < 2000 ? '⬇ leicht gedrosselt' : '✅ volle Leistung';
    h1600Reason = lim1600 < 1600 ? '⬇ leicht gedrosselt' : '✅ volle Leistung';
  }
 
  document.getElementById('inv-status').textContent = statusText;
  document.getElementById('inv-se-reason').textContent = seReason;
  if (state.has_l2) {
    document.getElementById('inv-se-l2-reason').textContent = seReasonL2;
  }
  document.getElementById('inv-2000-reason').textContent = h2000Reason;
  document.getElementById('inv-1600-reason').textContent = h1600Reason;
 
  setInv('inv-se',   seIst,   seLim,  2400);
  if (state.has_l2) {
    setInv('inv-se-l2', seIstL2, seLimL2, 2400);
  }
  setInv('inv-2000', h2000Ist, lim2000, 2000);
  setInv('inv-1600', h1600Ist, lim1600, 1600);
}

function setInv(prefix, ist, lim, max) {
  document.getElementById(prefix + '-ist').textContent = Math.round(ist);
  document.getElementById(prefix + '-lim').textContent = Math.round(lim);
  const pct = lim > 0 ? Math.min(100, ist / lim * 100) : (ist > 0 ? 100 : 0);
  const color = pct > 95 ? '#ff3d57' : pct > 70 ? '#f0a500' : '#00e676';
  const bar = document.getElementById(prefix + '-bar');
  bar.style.width = Math.min(100, ist / max * 100) + '%';
  bar.style.background = color;
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

async function deleteLog() {
  if (!confirm('CSV-Log wirklich löschen?')) return;
  try {
    const r = await fetch('log/delete', { method: 'POST' });
    const d = await r.json();
    if (d.status === 'ok') alert('Log gelöscht!');
    else alert('Fehler: ' + d.message);
  } catch(e) { alert('Fehler!'); }
}

async function refresh() {
  try {
    // v1.9.2: relative Pfade — funktionieren direkt (Port 8765) UND via HA-Ingress
    const stateR = await fetch('state').then(r => r.json());
    // Immer state anzeigen, auch ohne CSV
    updateCards(stateR, {});
    document.getElementById('ts').textContent = 'Letzte Aktualisierung: ' + new Date().toLocaleTimeString('de-DE');
    
    try {
      const apiR = await fetch('api').then(r => r.json());
      if (apiR.rows && apiR.rows.length > 0) {
        updateCards(stateR, apiR.rows[apiR.rows.length - 1]);
        updateCharts(apiR.rows);
      }
    } catch(e) {
      console.log('API Fehler:', e);
    }
  } catch(e) {
    console.log('State Fehler:', e);
  }
}

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>"""


def get_split_power(requester_ip, real_grid_power, opts) -> float:
    mode = opts.get("proxy_split_mode", "soc")
    if mode == "off":
        return real_grid_power
        
    state = load_state()
    ip_l1 = opts.get("sunenergy_ip", "192.168.178.94")
    ip_l2 = opts.get("sunenergy_ip_l2", "")
    has_l2 = bool(ip_l2)
    
    if not has_l2:
        return real_grid_power

    if requester_ip not in (ip_l1, ip_l2):
        return real_grid_power
        
    online_l1 = state.get("l1_polling_ok", True)
    online_l2 = state.get("l2_polling_ok", True)
    
    # v2.1.5: Berücksichtige leere Speicher bei Netzbezug (Entkopplung von PV-Drossel)
    if real_grid_power > 0:
        active_l1 = online_l1 and state.get("discharge_active_l1", True)
        active_l2 = online_l2 and state.get("discharge_active_l2", True)
        
        if active_l1 and not active_l2:
            return real_grid_power if requester_ip == ip_l1 else 0.0
        if active_l2 and not active_l1:
            return real_grid_power if requester_ip == ip_l2 else 0.0
        if not active_l1 and not active_l2:
            return real_grid_power
    else:
        # Bei Netzeinspeisung / Laden zählen nur die Online-Zustände
        if online_l1 and not online_l2:
            return real_grid_power if requester_ip == ip_l1 else 0.0
        if online_l2 and not online_l1:
            return real_grid_power if requester_ip == ip_l2 else 0.0
        if not online_l1 and not online_l2:
            return real_grid_power
        
    if mode == "static":
        return real_grid_power * 0.5
        
    soc_l1 = float(state.get("soc", 50.0))
    soc_l2 = float(state.get("soc_l2", 50.0))
    soc_min = float(opts.get("soc_min", 10.0))
    soc_max = float(opts.get("soc_normal_max", 95.0))
    
    # Kreuzladungs-Erkennung & Richtungs-Koordination (Breakout)
    op_l1 = float(state.get("op_l1", 0.0))
    pv_l1 = float(state.get("pv_l1", 0.0))
    iw_l1 = float(state.get("iw_l1", 0.0))
    ac_charge_l1 = max(0.0, iw_l1 - pv_l1)
    
    op_l2 = float(state.get("op_l2", 0.0))
    pv_l2 = float(state.get("pv_l2", 0.0))
    iw_l2 = float(state.get("iw_l2", 0.0))
    ac_charge_l2 = max(0.0, iw_l2 - pv_l2)
    
    is_cross_charging = False
    anteil_l1 = 0.5
    anteil_l2 = 0.5
    
    if op_l1 > 100.0 and ac_charge_l2 > 100.0:
        is_cross_charging = True
        if real_grid_power > 0:
            # L1 entlädt, L2 lädt aus dem Netz. Bei Import: L1 bekommt 0, L2 bekommt den gesamten Wert (damit L2 das Laden stoppt)
            anteil_l1 = 0.0
            anteil_l2 = 1.0
        else:
            # Bei Export: L1 bekommt den gesamten Wert (damit L1 das Entladen stoppt), L2 bekommt 0
            anteil_l1 = 1.0
            anteil_l2 = 0.0
    elif op_l2 > 100.0 and ac_charge_l1 > 100.0:
        is_cross_charging = True
        if real_grid_power > 0:
            # L2 entlädt, L1 lädt aus dem Netz. Bei Import: L2 bekommt 0, L1 bekommt den gesamten Wert (damit L1 das Laden stoppt)
            anteil_l1 = 1.0
            anteil_l2 = 0.0
        else:
            # Bei Export: L2 bekommt den gesamten Wert (damit L2 das Entladen stoppt), L1 bekommt 0
            anteil_l1 = 0.0
            anteil_l2 = 1.0
            
    if is_cross_charging:
        pass
    elif real_grid_power > 0:
        usable_l1 = max(0.0, soc_l1 - soc_min)
        usable_l2 = max(0.0, soc_l2 - soc_min)
        total = usable_l1 + usable_l2
        if total <= 0:
            return real_grid_power
        anteil_l1 = usable_l1 / total
        anteil_l2 = usable_l2 / total
    else:
        headroom_l1 = max(0.0, soc_max - soc_l1)
        headroom_l2 = max(0.0, soc_max - soc_l2)
        total = headroom_l1 + headroom_l2
        if total <= 0:
            return real_grid_power
        anteil_l1 = headroom_l1 / total
        anteil_l2 = headroom_l2 / total
        
    if requester_ip == ip_l1:
        return real_grid_power * anteil_l1
    else:
        return real_grid_power * anteil_l2


class UIHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        opts = load_options()
        shelly_ip = opts.get("shelly_ip", "192.168.178.98")

        if self.path == "/meter":
            power = get_shelly_power(shelly_ip)
            
            client_ip = self.client_address[0]
            ip_l1 = opts.get("sunenergy_ip", "192.168.178.94")
            ip_l2 = opts.get("sunenergy_ip_l2", "")
            
            proxy_st = load_proxy_state()
            updates = {}
            if client_ip == ip_l1:
                updates["last_poll_l1_ts"] = time.time()
                updates["consecutive_polls_l1"] = proxy_st.get("consecutive_polls_l1", 0) + 1
            elif ip_l2 and client_ip == ip_l2:
                updates["last_poll_l2_ts"] = time.time()
                updates["consecutive_polls_l2"] = proxy_st.get("consecutive_polls_l2", 0) + 1
                
            if updates:
                save_proxy_state(updates)
                
            if opts.get("use_native_pid", False):
                power = get_split_power(client_ip, power, opts)

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

        elif self.path == "/analyse" or self.path == "/analysis":
            html_path = Path(__file__).parent / "analyse.html"
            if html_path.exists():
                with open(html_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Analyse-Datei nicht gefunden")

        elif self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode())

        elif self.path == "/state":
            st = load_state()
            pst = load_proxy_state()
            st.update(pst)
            # soc_normal_max aus Optionen mitgeben, damit das Frontend "SOC voll" erkennt
            try:
                st["soc_normal_max"] = float(opts.get("soc_normal_max", 95))
            except Exception:
                st["soc_normal_max"] = 95
            st["has_l2"] = bool(opts.get("sunenergy_ip_l2", ""))
            self._json(st)

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

        elif self.path == "/log/delete":
            # v1.9.2: Zustandsändernde Aktion nur noch via POST (siehe do_POST).
            # GET liefert 405, damit Browser-Prefetch/Link-Preview nichts löscht.
            self.send_response(405)
            self.send_header("Allow", "POST")
            self.end_headers()
            self.wfile.write(b"Use POST")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/log/delete":
            try:
                if os.path.exists(CSV_PATH):
                    os.remove(CSV_PATH)
                self._json({"status": "ok", "message": "Log gelöscht"})
            except Exception as e:
                self._json({"status": "error", "message": str(e)})
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
    # ThreadingHTTPServer: ein hängender /meter-Poll (Shelly-Timeout) blockiert
    # nicht mehr das Dashboard — und umgekehrt.
    server = ThreadingHTTPServer(("0.0.0.0", 8765), UIHandler)
    print("Web UI läuft auf http://0.0.0.0:8765")
    server.serve_forever()

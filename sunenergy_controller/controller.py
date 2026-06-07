#!/usr/bin/env python3
"""
SunEnergy XT Controller v1.8.4
=============================
Universelle Nulleinspeisung für SunEnergyXT 500 Pro + Hoymiles HMS.

Regelkonzept:
- GS = OP + grid_p  → Akku entlädt/lädt je nach Bedarf (bei JEDEM SOC)
- IS                → begrenzt DC-Carport wenn zu viel produziert wird
- HMS               → drosselt Hoymiles wenn zu viel produziert wird
- Nachts            → MM=AN, Gerät regelt selbst bis SO (10%)
- Zwangsladung      → alle calibration_days Tage auf 100%
"""

import json
import csv
import logging
import os
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("sunenergy_controller")

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
OPTIONS_PATH = "/data/options.json"
STATE_PATH   = "/data/controller_state.json"
CSV_PATH     = "/data/controller_log.csv"
TICK_S       = 5

def load_options() -> dict:
    with open(OPTIONS_PATH) as f:
        return json.load(f)

def load_state() -> dict:
    try:
        if Path(STATE_PATH).exists():
            with open(STATE_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "active_mode": "night",
        "last_calibration_ts": time.time(),
        "grid_p_filtered": 0.0,
        "solar_p_last": 0.0,
        "haus_p_last": 0.0,
        "last_gs": 0.0,
        "soc": 0.0,
        "pv_last": 0.0,
    }

def save_state(state: dict):
    try:
        with open(STATE_PATH, "w") as f:
            json.dump(state, f)
    except Exception as e:
        log.error("State speichern Fehler: %s", e)

# ---------------------------------------------------------------------------
# CSV Logging
# ---------------------------------------------------------------------------
CSV_FIELDS = [
    "ts", "mode", "soc", "grid_p", "haus_p", "solar_p",
    "gs", "op", "pv", "is_target", "hms_limit", "hms_2000", "hms_1600",
    "hms_2000_lim", "hms_1600_lim"
]

def csv_log(row: dict):
    try:
        write_header = not os.path.exists(CSV_PATH)
        if os.path.exists(CSV_PATH):
            try:
                with open(CSV_PATH, "r") as f:
                    header = f.readline().strip().split(",")
                if header != CSV_FIELDS:
                    log.warning("CSV Header veraltet. Lösche alte CSV-Datei.")
                    os.remove(CSV_PATH)
                    write_header = True
            except Exception as e:
                log.error("Fehler beim Überprüfen des CSV-Headers: %s", e)
        with open(CSV_PATH, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
            if write_header:
                w.writeheader()
            w.writerow(row)
    except Exception as e:
        log.debug("CSV log Fehler: %s", e)

# ---------------------------------------------------------------------------
# Home Assistant API
# ---------------------------------------------------------------------------
HA_URL   = "http://supervisor/core"
HA_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
DRY_RUN  = False

def ha_get_state(entity_id: str, default=None):
    try:
        r = requests.get(
            f"{HA_URL}/api/states/{entity_id}",
            headers={"Authorization": f"Bearer {HA_TOKEN}"},
            timeout=5,
        )
        if r.status_code == 200:
            state = r.json().get("state")
            if state not in ("unknown", "unavailable", None):
                return state
    except Exception as e:
        log.error("HA GET %s: %s", entity_id, e)
    return default

def ha_get_full(entity_id: str):
    try:
        r = requests.get(
            f"{HA_URL}/api/states/{entity_id}",
            headers={"Authorization": f"Bearer {HA_TOKEN}"},
            timeout=5,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def ha_set_number(entity_id: str, value: float) -> bool:
    if DRY_RUN:
        log.info("🔍 [DRY-RUN] WÜRDE setzen: %s = %s", entity_id, round(value, 1))
        return True
    try:
        r = requests.post(
            f"{HA_URL}/api/services/number/set_value",
            headers={"Authorization": f"Bearer {HA_TOKEN}"},
            json={"entity_id": entity_id, "value": round(value, 1)},
            timeout=5,
        )
        if r.status_code not in (200, 201):
            log.error("HA SET %s fehlgeschlagen mit Status %s: %s", entity_id, r.status_code, r.text)
        return r.status_code in (200, 201)
    except Exception as e:
        log.error("HA SET %s: %s", entity_id, e)
        return False

def ha_switch(entity_id: str, turn_on: bool) -> bool:
    if DRY_RUN:
        log.info("🔍 [DRY-RUN] WÜRDE schalten: %s = %s", entity_id, "AN" if turn_on else "AUS")
        return True
    action = "turn_on" if turn_on else "turn_off"
    try:
        r = requests.post(
            f"{HA_URL}/api/services/switch/{action}",
            headers={"Authorization": f"Bearer {HA_TOKEN}"},
            json={"entity_id": entity_id},
            timeout=5,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        log.error("HA SWITCH %s: %s", entity_id, e)
        return False

# ---------------------------------------------------------------------------
# SunEnergyXT direkt schreiben
# ---------------------------------------------------------------------------
def sunenergy_write(ip: str, payload: dict) -> bool:
    if DRY_RUN:
        log.info("🔍 [DRY-RUN] WÜRDE SunEnergyXT schreiben: %s", payload)
        return True
    try:
        r = requests.post(
            f"http://{ip}/write",
            json={"state": payload},
            timeout=5,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        log.error("SunEnergyXT WRITE Fehler: %s", e)
        return False

def sunenergy_read(ip: str) -> dict:
    """Liest den aktuellen Status vom SunEnergyXT."""
    try:
        r = requests.get(f"http://{ip}/read", timeout=5)
        if r.status_code == 200:
            return r.json().get("state", {}).get("reported", {})
    except Exception as e:
        log.error("SunEnergyXT READ Fehler: %s", e)
    return {}

# ---------------------------------------------------------------------------
# Sonnenstand
# ---------------------------------------------------------------------------
def get_sun_state() -> dict:
    data = ha_get_full("sun.sun")
    if data:
        return data
    return {"state": "below_horizon"}

# ---------------------------------------------------------------------------
# HMS Limits berechnen
# ---------------------------------------------------------------------------
def calc_hms_limits(
    hms_limit_target: float,
    solar_p_2000: float,
    solar_p_1600: float,
    hms_2000_online: bool,
    hms_1600_online: bool,
) -> tuple[float, float]:
    """Teilt das berechnete Gesamt-HMS-Limit stufenlos auf die beiden Inverter auf."""
    max_2000 = 2000.0
    max_1600 = 1600.0

    # Wenn das Gesamtlimit auf Maximum steht, öffnen wir beide Wechselrichter voll.
    # Dies verhindert unnötige Regelschwankungen/Proportional-Updates bei wolkenbedingter Solaränderung.
    if hms_limit_target >= 3600.0:
        return (max_2000 if hms_2000_online else 0.0), (max_1600 if hms_1600_online else 0.0)

    total_solar = (solar_p_2000 if hms_2000_online else 0) + (solar_p_1600 if hms_1600_online else 0)
    
    if total_solar > 50:
        ratio_2000 = (solar_p_2000 / total_solar) if hms_2000_online else 0
        ratio_1600 = (solar_p_1600 / total_solar) if hms_1600_online else 0
    else:
        if hms_2000_online and hms_1600_online:
            ratio_2000 = 0.55
            ratio_1600 = 0.45
        elif hms_2000_online:
            ratio_2000 = 1.0
            ratio_1600 = 0.0
        elif hms_1600_online:
            ratio_2000 = 0.0
            ratio_1600 = 1.0
        else:
            ratio_2000 = 0.0
            ratio_1600 = 0.0

    limit_2000 = 0.0
    limit_1600 = 0.0

    if hms_2000_online:
        limit_2000 = min(int(hms_limit_target * ratio_2000), max_2000)
        limit_2000 = max(0.0, limit_2000)

    if hms_1600_online:
        limit_1600 = min(int(hms_limit_target * ratio_1600), max_1600)
        limit_1600 = max(0.0, limit_1600)

    return limit_2000, limit_1600



# ---------------------------------------------------------------------------
# Hauptregelschleife
# ---------------------------------------------------------------------------
def main():
    global DRY_RUN
    log.info("SunEnergy XT Controller v2.0 startet...")
    opts  = load_options()
    state = load_state()

    DRY_RUN = bool(opts.get("dry_run", True))
    if DRY_RUN:
        log.info("DRY-RUN Modus aktiv - es wird NICHTS geschrieben!")
    else:
        log.info("Aktiver Modus - Controller schreibt in HA")

    # Konfiguration
    grid_sensor     = opts["grid_sensor"]
    soc_sensor      = opts["soc_sensor"]
    gs_entity       = opts["gs_entity"]
    mm_switch       = opts["mm_switch"]
    sa_entity       = opts["sa_entity"]
    hms_2000_entity = opts["hms_2000_entity"]
    hms_1600_entity = opts["hms_1600_entity"]
    
    # Neue konfigurierbare Sensoren
    haus_power_sensor     = opts.get("haus_power_sensor", "sensor.hausverbrauch_aktuell")
    hms_2000_power_sensor = opts.get("hms_2000_power_sensor", "sensor.hoymiles_hms_2000_4t_power")
    hms_1600_power_sensor = opts.get("hms_1600_power_sensor", "sensor.hoymiles_hms_1600_4t_power")
    hms_2000_reachable_sensor = opts.get("hms_2000_reachable_sensor", "binary_sensor.hoymiles_hms_2000_4t_reachable")
    hms_1600_reachable_sensor = opts.get("hms_1600_reachable_sensor", "binary_sensor.hoymiles_hms_1600_4t_reachable")

    soc_normal_max  = float(opts["soc_normal_max"])    # 95%
    soc_min         = float(opts["soc_min"])            # 10%
    calib_days      = float(opts["calibration_days"])  # 15
    sunenergy_ip    = opts.get("sunenergy_ip", "192.168.178.94")

    # SA auf Normalwert setzen beim Start
    ha_set_number(sa_entity, soc_normal_max)
    sunenergy_write(sunenergy_ip, {"SA": int(soc_normal_max)})

    # State initialisieren (falls nicht aus vorherigem Lauf geladen)
    if "last_calibration_ts" not in state:
        state["last_calibration_ts"] = time.time()
    if "last_hms_limit" not in state:
        state["last_hms_limit"] = 3600.0
    if "last_hms_2000_lim" not in state:
        state["last_hms_2000_lim"] = 2000.0
    if "last_hms_1600_lim" not in state:
        state["last_hms_1600_lim"] = 1600.0
    if "manual_feed_in_active" not in state:
        state["manual_feed_in_active"] = False
    if "manual_feed_in_accumulated_kwh" not in state:
        state["manual_feed_in_accumulated_kwh"] = 0.0

    # Fix #4: Device-State explizit auf None setzen damit der erste Tick
    # immer schreibt (None != jeder Wert → Write-Bedingung immer True)
    state["last_device_gs"] = None
    state["last_device_mm"] = None
    state["last_device_is"] = None

    state["active_mode"] = "night"
    save_state(state)
    log.info("Addon gestartet, SA=%s%%, HMS-Limit=%sW", soc_normal_max, state["last_hms_limit"])

    # Lokaler Cache für SunEnergyXT Daten zur Entlastung bei API-Ausfällen (Option C)
    op_current = 0.0
    pv_current = float(state.get("pv_last", 0.0))
    pb_current = 0.0

    while True:
        try:
            tick_start = time.monotonic()

            # ------------------------------------------------------------------
            # 1. Messwerte lesen
            # ------------------------------------------------------------------            # 1. Messwerte lesen
            grid_val = ha_get_state(grid_sensor)
            if grid_val not in (None, "unknown", "unavailable"):
                grid_p_raw = float(grid_val)
            else:
                grid_p_raw = float(state.get("grid_p_filtered", 0.0))

            soc_val = ha_get_state(soc_sensor)
            if soc_val not in (None, "unknown", "unavailable"):
                curr_soc = float(soc_val)
                state["soc"] = curr_soc
            else:
                curr_soc = float(state.get("soc", 0.0))

            # (Hausverbrauch wird weiter unten lokal und verzögerungsfrei berechnet)

            # Hysteresis für niedrigen SOC (Entladeschutz)
            low_soc_active = state.get("low_soc_active", False)
            if curr_soc <= soc_min:
                low_soc_active = True
            elif curr_soc >= (soc_min + 2.0): # erst ab 12% wieder freigeben
                low_soc_active = False
            state["low_soc_active"] = low_soc_active

            solar_2000_val = ha_get_state(hms_2000_power_sensor)
            if solar_2000_val not in (None, "unknown", "unavailable"):
                solar_p_2000 = abs(float(solar_2000_val))
            else:
                solar_p_2000 = float(state.get("solar_p_2000_last", 0.0))

            solar_1600_val = ha_get_state(hms_1600_power_sensor)
            if solar_1600_val not in (None, "unknown", "unavailable"):
                solar_p_1600 = abs(float(solar_1600_val))
            else:
                solar_p_1600 = float(state.get("solar_p_1600_last", 0.0))
            
            # Robustes Checken: Wenn Leistung > 10W, ist er online. Ansonsten aus HA lesen.
            hms_2000_online = (ha_get_state(hms_2000_reachable_sensor, "off") == "on") or (solar_p_2000 > 10.0)
            hms_1600_online = (ha_get_state(hms_1600_reachable_sensor, "off") == "on") or (solar_p_1600 > 10.0)
            
            solar_p = (solar_p_2000 if hms_2000_online else 0) + (solar_p_1600 if hms_1600_online else 0)

            # Watchdog
            shelly_data = ha_get_full(grid_sensor)
            if shelly_data:
                last_upd = shelly_data.get("last_updated", "")
                try:
                    upd_ts = datetime.fromisoformat(last_upd.replace("Z", "+00:00")).timestamp()
                    watchdog_ok = (time.time() - upd_ts) < 60
                except Exception:
                    watchdog_ok = False
            else:
                watchdog_ok = False

            # ------------------------------------------------------------------
            # 2. Sicherheits-Stopp
            # ------------------------------------------------------------------
            if not watchdog_ok:
                log.warning("Watchdog Fehler! Sicherheits-Stopp.")
                ha_switch(mm_switch, True)
                ha_set_number(gs_entity, 0)
                sunenergy_write(sunenergy_ip, {"IS": 2400, "MM": 1, "GS": 0})
                time.sleep(TICK_S)
                continue

            # ------------------------------------------------------------------
            # 3. SunEnergyXT Status lesen (OP = aktueller AC-Ausgang)
            # ------------------------------------------------------------------
            se_data = sunenergy_read(sunenergy_ip)
            if se_data:
                op_current = float(se_data.get("OP", 0))
                pv_current = float(se_data.get("PV", 0))
                pb_current = float(se_data.get("BP", 0))
            else:
                log.warning("SunEnergyXT API nicht erreichbar, verwende letzte Werte (OP=%.1fW, PV=%.1fW, BP=%.1fW)", 
                            op_current, pv_current, pb_current)
            
            state["soc"] = curr_soc
            state["pv_last"] = pv_current

            # Berechne den Hausverbrauch lokal und verzögerungsfrei (ohne den trägen Shelly 1PM)
            # battery_ac_est ist positiv bei Entladung (OP) und negativ bei Ladung (-BP)
            battery_ac_est = op_current if op_current > 5.0 else -pb_current
            haus_p = max(0.0, grid_p_raw + solar_p + battery_ac_est)

            # ------------------------------------------------------------------
            # 3b. Manuelle Einspeisung prüfen und integrieren
            # ------------------------------------------------------------------
            manual_feed_in_switch = opts.get("manual_feed_in_switch", "input_boolean.sunenergy_manual_feed_in")
            manual_feed_in_target = float(opts.get("manual_feed_in_target", 0.5))
            manual_feed_in_min_soc = float(opts.get("manual_feed_in_min_soc", 90.0))
            manual_feed_in_power = float(opts.get("manual_feed_in_power", 500.0))

            feed_in_active = False
            if manual_feed_in_switch:
                feed_in_state = ha_get_state(manual_feed_in_switch, "off")
                feed_in_active = (feed_in_state == "on")

            grid_target = 0.0
            is_actively_feeding_in = False

            if feed_in_active:
                if not state.get("manual_feed_in_active", False):
                    # Transition von Aus auf An
                    state["manual_feed_in_active"] = True
                    state["manual_feed_in_accumulated_kwh"] = 0.0
                    log.info("🔋 Manuelle Einspeisung gestartet. Ziel: %.2f kWh (Leistung: %.0fW, Mindest-SOC: %.0f%%)", 
                             manual_feed_in_target, manual_feed_in_power, manual_feed_in_min_soc)

                # Überschuss-Bedingung: Gesamte Erzeugung (Hoymiles + DC-PV) übersteigt Hausverbrauch
                surplus = (solar_p + pv_current) - haus_p
                conditions_met = (curr_soc >= manual_feed_in_min_soc) and (surplus > 0.0)
                if conditions_met:
                    is_actively_feeding_in = True
                    grid_target = -min(manual_feed_in_power, surplus)
                    
                    if grid_p_raw < 0:
                        tick_kwh = (-grid_p_raw * TICK_S) / 3600000.0
                        state["manual_feed_in_accumulated_kwh"] = state.get("manual_feed_in_accumulated_kwh", 0.0) + tick_kwh

                accumulated = state.get("manual_feed_in_accumulated_kwh", 0.0)
                if is_actively_feeding_in:
                    log.info("🔋 Manuelle Einspeisung aktiv: %.4f / %.2f kWh (Ziel-Netz: -%.0f W, Aktuell: %.0f W)", 
                             accumulated, manual_feed_in_target, manual_feed_in_power, grid_p_raw)
                else:
                    log.info("🔋 Manuelle Einspeisung im Standby: %.4f / %.2f kWh (SOC: %.1f%%/%.0f%%, Solar gesamt: %.0fW/Haus: %.0fW)",
                             accumulated, manual_feed_in_target, curr_soc, manual_feed_in_min_soc, (solar_p + pv_current), haus_p)

                if accumulated >= manual_feed_in_target:
                    log.info("🔋 Manuelle Einspeisung Ziel von %.2f kWh erreicht! Schalte ab...", manual_feed_in_target)
                    if not DRY_RUN:
                        requests.post(
                            f"{HA_URL}/api/services/input_boolean/turn_off",
                            headers={"Authorization": f"Bearer {HA_TOKEN}"},
                            json={"entity_id": manual_feed_in_switch},
                            timeout=5,
                        )
                    state["manual_feed_in_active"] = False
                    state["manual_feed_in_accumulated_kwh"] = 0.0
                    feed_in_active = False
                    is_actively_feeding_in = False
                    grid_target = 0.0
            else:
                if state.get("manual_feed_in_active", False):
                    # Transition von An auf Aus
                    state["manual_feed_in_active"] = False
                    state["manual_feed_in_accumulated_kwh"] = 0.0
                    log.info("🔋 Manuelle Einspeisung gestoppt.")


            # ------------------------------------------------------------------
            # 4. Sonnenstand
            # ------------------------------------------------------------------
            sun_above = get_sun_state().get("state") == "above_horizon"

            # ------------------------------------------------------------------
            # 5. Zwangsladung prüfen
            # ------------------------------------------------------------------
            tage_seit = (time.time() - state["last_calibration_ts"]) / 86400
            zwangsladung_trigger = (
                tage_seit > calib_days
                and not sun_above
                and curr_soc < 100
                and state["active_mode"] != "calibration"
            )
            if zwangsladung_trigger:
                log.info("Zwangsladung gestartet! %.1f Tage seit letzter Vollladung", tage_seit)
                state["active_mode"] = "calibration"
                save_state(state)

            if state["active_mode"] == "calibration" and curr_soc < 100:
                log.info("Zwangsladung läuft... SOC=%.1f%%", curr_soc)
                ha_set_number(sa_entity, 100)
                ha_switch(mm_switch, False)
                ha_set_number(gs_entity, -2400)
                # Fix #1: GS auch direkt ans Gerät schreiben (nicht nur HA)
                sunenergy_write(sunenergy_ip, {"GS": -2400, "MM": 0})
                state["last_device_gs"] = -2400
                state["last_device_mm"] = 0
                time.sleep(TICK_S)
                continue

            if state["active_mode"] == "calibration" and curr_soc >= 100:
                log.info("Zwangsladung abgeschlossen!")
                state["last_calibration_ts"] = time.time()
                state["active_mode"] = "night"
                ha_set_number(sa_entity, soc_normal_max)
                ha_switch(mm_switch, True)
                ha_set_number(gs_entity, 0)
                sunenergy_write(sunenergy_ip, {"SA": int(soc_normal_max), "IS": 2400, "GS": 0})
                # Fix #2+#5: State zurücksetzen damit nächster Tick alle Werte neu schreibt
                state["last_device_gs"] = None
                state["last_device_mm"] = None
                state["last_device_is"] = None
                save_state(state)
                time.sleep(TICK_S)
                continue

            # ------------------------------------------------------------------
            # 6. Nachtmodus — Gerät regelt selbst via MM=1 ( materialschonend )
            # ------------------------------------------------------------------
            if not sun_above:
                if state["active_mode"] != "night":
                    log.info("Nachtmodus aktiv: MM=0, wir regeln die Entladung aktiv")
                    
                    # MM ausschalten (für manuelle Regelung über GS)
                    current_mm_state = ha_get_state(mm_switch, "on")
                    if current_mm_state != "off":
                        ha_switch(mm_switch, False)
                    
                    # Hoymiles auf Maximum setzen
                    ha_set_number(hms_2000_entity, 2000)
                    if hms_1600_online:
                        ha_set_number(hms_1600_entity, 1600)
                    
                    # IS auf Maximum
                    sunenergy_write(sunenergy_ip, {"MM": 0, "IS": 2400})
                    
                    state["active_mode"] = "night"
                    state["last_device_mm"] = 0
                    state["last_device_is"] = 2400
                    # Fix #3: last_device_gs auf None → erster GS-Write im Nachtmodus
                    # wird nicht übersprungen
                    state["last_device_gs"] = None
                    state["last_hms_2000_lim"] = 2000
                    state["last_hms_1600_lim"] = 1600
                    state["last_hms_limit"] = 3600.0

                # GS nachts aktiv regeln
                gs_last = float(state.get("last_gs", 0))
                gs_new = gs_last + grid_p_raw * 0.5
                if low_soc_active:
                    gs_new = min(0.0, gs_new)
                gs_new = max(-2400, min(2400, gs_new))
                
                gs_new_rounded = round(gs_new / 10) * 10
                
                device_payload_night = {}
                if state.get("last_device_gs") != gs_new_rounded:
                    device_payload_night["GS"] = gs_new_rounded
                    state["last_device_gs"] = gs_new_rounded
                
                is_target_night = 10 if low_soc_active else 2400
                if state.get("last_device_is") != is_target_night:
                    device_payload_night["IS"] = is_target_night
                    state["last_device_is"] = is_target_night
                    
                if state.get("last_device_mm") != 0:
                    device_payload_night["MM"] = 0
                    state["last_device_mm"] = 0
                    
                if device_payload_night:
                    sunenergy_write(sunenergy_ip, device_payload_night)

                if state.get("last_gs_written") is None or abs(state["last_gs_written"] - gs_new_rounded) >= 10:
                    ha_set_number(gs_entity, gs_new_rounded)
                    state["last_gs_written"] = gs_new_rounded

                log.info("Nacht: Aktive Regelung (MM=0) | GS=%dW IS=%dW | grid=%.0fW haus=%.0fW SOC=%.0f%%",
                         gs_new_rounded, is_target_night, grid_p_raw, haus_p, curr_soc)

                # CSV schreiben
                csv_log({
                    "ts":       time.strftime("%Y-%m-%d %H:%M:%S"),
                    "mode":     "night",
                    "soc":      round(curr_soc, 1),
                    "grid_p":   round(grid_p_raw, 1),
                    "haus_p":   round(haus_p, 1),
                    "solar_p":  round(solar_p, 1),
                    "gs":       round(gs_new_rounded, 0),
                    "op":       round(op_current, 1),
                    "pv":       round(pv_current, 1),
                    "is_target": is_target_night,
                    "hms_limit": 3600,
                    "hms_2000":  round(solar_p_2000, 1),
                    "hms_1600":  round(solar_p_1600, 1),
                    "hms_2000_lim": 2000,
                    "hms_1600_lim": 1600,
                })

                state["grid_p_filtered"] = grid_p_raw
                state["last_gs"]         = gs_new
                save_state(state)
                time.sleep(TICK_S)
                continue

            # ------------------------------------------------------------------
            # 7. Tagregelung — universell für jeden SOC mit Spam-Schutz
            # ------------------------------------------------------------------
            if feed_in_active:
                state["active_mode"] = "feed_in" if is_actively_feeding_in else "feed_in_standby"
            else:
                state["active_mode"] = "active"

            # Netz-Fehler bezüglich des Soll-Netzwertes (0W bzw. -500W bei manueller Einspeisung)
            grid_error = grid_p_raw - grid_target

            # GS Formel: gedämpft → gs_last + grid_error * 0.5
            gs_last = float(state.get("last_gs", 0))
            gs_new = gs_last + grid_error * 0.5
            if low_soc_active:
                gs_new = min(0.0, gs_new)
            gs_new = max(-2400, min(2400, gs_new))

            # MM AUS — wir regeln (nur schalten, wenn nicht bereits aus)
            current_mm_state = ha_get_state(mm_switch, "on")
            if current_mm_state != "off":
                ha_switch(mm_switch, False)

            # GS Sollwert in HA schreiben (nur bei nennenswerten Änderungen)
            gs_new_rounded = round(gs_new / 10) * 10
            if state.get("last_gs_written") is None or abs(state["last_gs_written"] - gs_new_rounded) >= 10:
                ha_set_number(gs_entity, gs_new_rounded)
                state["last_gs_written"] = gs_new_rounded

            # HMS stufenlos regeln
            hms_limit_last = float(state.get("last_hms_limit", 3600.0))
            hms_change = 0.0

            # Bei aktiver manueller Einspeisung Hoymiles voll öffnen
            if is_actively_feeding_in:
                hms_limit_new = 3600.0
            elif grid_error < -50:
                # Priorisierung: Akku-Entladung reduzieren vor Hoymiles-Drosselung
                # Der Akku kann seine Entladung reduzieren, wenn der Sollwert positiv ist
                # und die aktuelle Entladung über dem solaren Zufluss (PV) liegt.
                battery_can_reduce_discharge = (gs_new_rounded > 0) and (op_current > pv_current + 20.0)
                if battery_can_reduce_discharge:
                    # Der Akku kann die Drosselung über die Reduzierung seiner Entladung abfangen.
                    # Wir drosseln die Hoymiles noch nicht, sondern lassen das Limit unverändert.
                    hms_limit_new = hms_limit_last
                else:
                    # Einspeisung: Hoymiles drosseln (mit Anti-Windup durch Baseline-Klemmen auf aktuelle Solarleistung + 100W)
                    # Fix #8: Baseline nicht unter 300W fallen lassen — verhindert zu aggressives
                    # Drosseln bei plötzlichem Wolkendurchgang (solar_p ≈ 0)
                    hms_limit_baseline = max(300.0, min(hms_limit_last, solar_p + 100.0))
                    hms_change = grid_error * 0.5
                    hms_change = max(-400.0, min(400.0, hms_change))
                    hms_limit_new = hms_limit_baseline + hms_change
            elif grid_error > 50:
                # Bezug: Hoymiles freigeben (mehr erzeugen lassen)
                hms_change = grid_error * 0.5
                hms_change = max(-400.0, min(800.0, hms_change))
                hms_limit_new = hms_limit_last + hms_change
            elif curr_soc < soc_normal_max:
                # Akku nicht voll und keine Abweichung vom Sollwert: stufenlos regeln
                # um Überschwingen/Oszillationen nahe der Vollladung zu verhindern.
                if solar_p >= hms_limit_last - 100:
                    hms_change = 80.0
                hms_change = max(-400.0, min(400.0, hms_change))
                hms_limit_new = hms_limit_last + hms_change
            else:
                hms_limit_new = hms_limit_last

            hms_limit_new = max(0.0, min(3600.0, hms_limit_new))
            state["last_hms_limit"] = hms_limit_new

            # HMS Limits berechnen
            limit_2000, limit_1600 = calc_hms_limits(
                hms_limit_new, solar_p_2000, solar_p_1600,
                hms_2000_online, hms_1600_online
            )

            # Drossel-Flag für HA/Visualisierung und Batterie-Entkoppelung setzen
            # Wir drosseln aktiv, wenn das Limit unter Maximum liegt UND die Hoymiles
            # tatsächlich an diesem Limit hängen (also mehr erzeugen könnten).
            drosseln = (hms_limit_new < 3500.0) and (solar_p >= hms_limit_new - 150.0) and (grid_error <= 50.0)
            state["drosseln"] = drosseln

            # IS Limit der Batterie anpassen
            if low_soc_active:
                is_target = 10
            elif is_actively_feeding_in:
                # Während aktiver manueller Einspeisung darf die Batterie maximal ihre eigene PV-Leistung abgeben,
                # um ein Entladen der Batterie-Zellen ins Netz zu verhindern.
                is_target = pv_current
            elif curr_soc >= (soc_normal_max - 3.0) or ((gs_new_rounded < -200) and (pb_current < 150.0)):
                if drosseln or ((gs_new_rounded < -200) and (pb_current < 150.0)):
                    # Wenn die Hoymiles gedrosselt sind ODER die Batterie
                    # die Ladung verweigert (BMS voll/gesperrt), darf die Batterie nur maximal ihre eigene
                    # PV-Leistung abgeben, um Einspeisung des Carport-Überschusses zu verhindern.
                    restbedarf = max(0, int(haus_p - solar_p))
                    is_target = min(pv_current, restbedarf)
                else:
                    # Wenn die Hoymiles voll offen sind und nicht ausreichen, liefert die Batterie den Rest
                    is_target = 2400
            else:
                # Normaler Betrieb: IS voll freigeben (2400W), damit der GS-Regler
                # die Nulleinspeisung ohne harten Limit-Konflikt (Wind-up) ausregeln kann
                is_target = 2400

            # Runden auf 10W-Schritte und Grenzwerte einhalten (10 bis 2400W)
            is_target = round(is_target / 10) * 10
            is_target = max(10, min(2400, is_target))
            
            # Sanfter Anstieg (Rate-Limit) um max +1000W pro Tick, um Firmware-Spikes beim Entdrosseln zu verhindern
            is_last = float(state.get("last_is", 2400.0))
            if is_target > is_last:
                is_target = min(is_target, is_last + 1000.0)
                is_target = round(is_target / 10) * 10
                
            state["last_is"] = is_target

            # Direkt ans Gerät schreiben (nur bei Änderungen)
            device_payload = {}
            if state.get("last_device_is") != is_target:
                device_payload["IS"] = is_target
                state["last_device_is"] = is_target
            if state.get("last_device_mm") != 0:
                device_payload["MM"] = 0
                state["last_device_mm"] = 0
            if state.get("last_device_gs") != gs_new_rounded:
                device_payload["GS"] = gs_new_rounded
                state["last_device_gs"] = gs_new_rounded
                
            if device_payload:
                sunenergy_write(sunenergy_ip, device_payload)

            # Hoymiles Limits setzen (mit Signalverlust-Schutz)
            # is_tick wird für Trägheitsprüfung verwendet
            is_tick = state.get("is_tick", 0) + 1
            state["is_tick"] = is_tick
            do_is_update = (is_tick % 6 == 0)

            if hms_2000_online:
                last_written_2000 = float(state.get("last_hms_2000_lim", 2000.0))
                # Senden wenn der neue Wert um >= 50W vom zuletzt geschriebenen abweicht
                # ODER wenn Inverter trotz Drosselung > 50W über Limit liegt
                need_send_2000 = (abs(last_written_2000 - limit_2000) >= 50) or (drosseln and solar_p_2000 > limit_2000 + 50 and do_is_update)
                if need_send_2000:
                    ha_set_number(hms_2000_entity, limit_2000)
                    state["last_hms_2000_lim"] = limit_2000

            if hms_1600_online:
                last_written_1600 = float(state.get("last_hms_1600_lim", 1600.0))
                need_send_1600 = (abs(last_written_1600 - limit_1600) >= 50) or (drosseln and solar_p_1600 > limit_1600 + 50 and do_is_update)
                if need_send_1600:
                    ha_set_number(hms_1600_entity, limit_1600)
                    state["last_hms_1600_lim"] = limit_1600

            log.info("GS=%dW IS=%dW HMS=%d/%dW (Target=%dW) | grid=%.0fW haus=%.0fW solar=%.0fW SOC=%.0f%%",
                     gs_new_rounded, is_target, limit_2000, limit_1600, int(hms_limit_new),
                     grid_p_raw, haus_p, solar_p, curr_soc)

            # Vollladung erkennen
            if curr_soc >= 100:
                state["last_calibration_ts"] = time.time()

            # CSV schreiben
            csv_log({
                "ts":       time.strftime("%Y-%m-%d %H:%M:%S"),
                "mode":     state["active_mode"],
                "soc":      round(curr_soc, 1),
                "grid_p":   round(grid_p_raw, 1),
                "haus_p":   round(haus_p, 1),
                "solar_p":  round(solar_p, 1),
                "gs":       round(gs_new_rounded, 0),
                "op":       round(op_current, 1),
                "pv":       round(pv_current, 1),
                "is_target": is_target,
                "hms_limit": round(limit_2000 + limit_1600, 0),
                "hms_2000":  round(solar_p_2000, 1),
                "hms_1600":  round(solar_p_1600, 1),
                "hms_2000_lim": round(limit_2000, 0),
                "hms_1600_lim": round(limit_1600, 0),
            })

            # last_hms_2000/1600_lim werden jetzt nur noch bei echten Schreibbefehlen aktualisiert (drift-safe)

            state["grid_p_filtered"] = grid_p_raw
            state["solar_p_last"]    = solar_p
            state["haus_p_last"]     = haus_p
            state["last_gs"]         = gs_new
            state["solar_p_2000_last"] = solar_p_2000
            state["solar_p_1600_last"] = solar_p_1600
            save_state(state)

        except Exception as e:
            log.error("Fehler im Regelzyklus: %s", e, exc_info=True)

        elapsed = time.monotonic() - tick_start
        time.sleep(max(0, TICK_S - elapsed))


if __name__ == "__main__":
    main()

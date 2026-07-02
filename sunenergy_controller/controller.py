#!/usr/bin/env python3
"""
SunEnergy XT Controller v2.5.7
=============================
Universelle Nulleinspeisung für SunEnergyXT 500 Pro + Hoymiles HMS.

Regelkonzept:
- GS = OP + grid_p  → Akku entlädt/lädt je nach Bedarf (bei JEDEM SOC)
- IS                → begrenzt DC-Carport wenn zu viel produziert wird
- HMS               → drosselt Hoymiles wenn zu viel produziert wird
- Nachts            → MM=0, aktive GS-Regelung der Entladung (bis low-SOC-Stopp)
- Zwangsladung      → alle calibration_days Tage auf 100%
- Shutdown/Watchdog → Übergabe an Geräte-Selbstregelung (MM=1)
"""

import json
import csv
import logging
import os
import signal
import time
import requests
from datetime import datetime, timezone, timedelta
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
PROXY_STATE_PATH = "/data/proxy_state.json"
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
        "op_l1": 0.0,
        "pv_l1": 0.0,
        "iw_l1": 0.0,
        "pb_l1": 0.0,
        "op_l2": 0.0,
        "pv_l2": 0.0,
        "iw_l2": 0.0,
        "pb_l2": 0.0,
    }

def load_proxy_state() -> dict:
    try:
        if Path(PROXY_STATE_PATH).exists():
            with open(PROXY_STATE_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_state(state: dict):
    try:
        temp_path = STATE_PATH + ".tmp"
        with open(temp_path, "w") as f:
            json.dump(state, f)
        os.replace(temp_path, STATE_PATH)
    except Exception as e:
        log.error("State speichern Fehler: %s", e)

# ---------------------------------------------------------------------------
# CSV Logging
# ---------------------------------------------------------------------------
CSV_FIELDS = [
    "ts", "mode", "soc", "grid_p", "haus_p", "solar_p",
    "gs", "op", "pv", "is_target", "hms_limit", "hms_2000", "hms_1600",
    "hms_2000_lim", "hms_1600_lim", "soc_l2", "op_l2", "pv_l2", "gs_l1", "gs_l2"
]

CSV_MAX_BYTES = 2 * 1024 * 1024   # 2 MB
CSV_KEEP_LINES = 2000             # Datenzeilen, die beim Trimmen erhalten bleiben

def trim_csv(path: str, keep_lines: int = CSV_KEEP_LINES):
    """Kürzt die CSV auf die letzten keep_lines Datenzeilen (Header bleibt erhalten),
    sobald sie zu groß wird. Verhindert unbegrenztes Wachstum / RAM-Bloat."""
    try:
        with open(path, "r", newline="") as f:
            lines = f.readlines()
        if len(lines) <= keep_lines + 1:
            return
        header = lines[0]
        tail = lines[-keep_lines:]
        with open(path, "w", newline="") as f:
            f.write(header)
            f.writelines(tail)
        log.info("CSV gekürzt auf letzte %d Zeilen (war zu groß).", keep_lines)
    except Exception as e:
        log.debug("trim_csv Fehler: %s", e)

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
        # Nach dem Schreiben: nur wenn Datei zu groß, kürzen (billiger getsize-Check)
        # if os.path.getsize(CSV_PATH) > CSV_MAX_BYTES:
        #     trim_csv(CSV_PATH)
    except Exception as e:
        log.debug("CSV log Fehler: %s", e)

# ---------------------------------------------------------------------------
# Home Assistant API
# ---------------------------------------------------------------------------
HA_URL   = "http://supervisor/core"
HA_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
# Sicherer Default: Bis main() die Option geladen hat, wird NICHTS geschrieben.
# Wird in main() aus den Optionen überschrieben.
DRY_RUN  = True

# v1.9.2: Persistente HTTP-Sessions (Keep-Alive statt TCP-Handshake pro Request).
# HA_SESSION trägt den Supervisor-Token, DEV_SESSION ist bewusst tokenfrei
# (Gerät/Shelly dürfen den HA-Token niemals sehen).
HA_SESSION = requests.Session()
HA_SESSION.headers.update({"Authorization": f"Bearer {HA_TOKEN}"})
DEV_SESSION = requests.Session()

# v1.9.2: Sauberer Shutdown via SIGTERM/SIGINT (run.sh leitet weiter)
RUNNING = True

def _handle_term(signum, frame):
    global RUNNING
    log.info("Signal %s empfangen — beende nach aktuellem Tick...", signum)
    RUNNING = False

def sleep_tick(seconds: float):
    """Unterbrechbarer Sleep: reagiert binnen ~0.2s auf SIGTERM."""
    end = time.monotonic() + max(0.0, seconds)
    while RUNNING and time.monotonic() < end:
        time.sleep(0.2)

# v2.1.5: Sofortiges Speichern für Echtzeit-Proxy-Aufteilung
def save_state_throttled(state: dict, every: int = 6):
    save_state(state)

def ha_get_state(entity_id: str, default=None):
    try:
        r = HA_SESSION.get(f"{HA_URL}/api/states/{entity_id}", timeout=5)
        if r.status_code == 200:
            state = r.json().get("state")
            if state not in ("unknown", "unavailable", None):
                return state
    except Exception as e:
        log.error("HA GET %s: %s", entity_id, e)
    return default

def ha_get_full(entity_id: str):
    try:
        r = HA_SESSION.get(f"{HA_URL}/api/states/{entity_id}", timeout=5)
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
        r = HA_SESSION.post(
            f"{HA_URL}/api/services/number/set_value",
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
        r = HA_SESSION.post(
            f"{HA_URL}/api/services/switch/{action}",
            json={"entity_id": entity_id},
            timeout=5,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        log.error("HA SWITCH %s: %s", entity_id, e)
        return False

def ha_push_sensor(entity_id: str, value: float, unit: str = "W", device_class: str = "power", friendly_name: str = "") -> bool:
    """Schreibt einen berechneten Wert als virtuellen HA-Sensor (POST /api/states).
    Kein input_number nötig — HA akzeptiert beliebige entity_ids über die REST API.
    Der Sensor bleibt bis zum nächsten HA-Neustart erhalten."""
    if DRY_RUN:
        return True
    try:
        payload = {
            "state": str(round(value, 1)),
            "attributes": {
                "unit_of_measurement": unit,
                "device_class": device_class,
                "state_class": "measurement",
                "friendly_name": friendly_name or entity_id,
            }
        }
        r = HA_SESSION.post(
            f"{HA_URL}/api/states/{entity_id}",
            json=payload,
            timeout=5,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        log.debug("ha_push_sensor %s: %s", entity_id, e)
        return False

# ---------------------------------------------------------------------------
# SunEnergyXT direkt schreiben
# ---------------------------------------------------------------------------
def sunenergy_write(ip: str, payload: dict) -> bool:
    if DRY_RUN:
        log.info("🔍 [DRY-RUN] WÜRDE SunEnergyXT schreiben: %s", payload)
        return True
    try:
        r = DEV_SESSION.post(
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
        r = DEV_SESSION.get(f"http://{ip}/read", timeout=5)
        if r.status_code == 200:
            return r.json().get("state", {}).get("reported", {})
    except Exception as e:
        log.error("SunEnergyXT READ Fehler: %s", e)
    return {}

# ---------------------------------------------------------------------------
# Shelly Pro 3EM Direkt-Fallback (v1.9.2)
# ---------------------------------------------------------------------------
def shelly_direct_power(ip: str):
    """Grid-Leistung direkt vom Shelly Pro 3EM lesen (RPC, ohne HA).
    Fallback wenn die HA-API stale ist (z.B. HA Core Neustart) — verhindert
    unnötige Safety-Stopps, obwohl der Zähler gesund ist."""
    try:
        r = DEV_SESSION.get(f"http://{ip}/rpc/EM.GetStatus?id=0", timeout=3)
        if r.status_code == 200:
            val = r.json().get("total_act_power")
            if val is not None:
                return float(val)
    except Exception as e:
        log.debug("Shelly Direkt-Fallback Fehler: %s", e)
    return None

# ---------------------------------------------------------------------------
# Sonnenstand
# ---------------------------------------------------------------------------
LAST_SUN_STATE = "below_horizon"

def get_sun_state() -> dict:
    global LAST_SUN_STATE
    data = ha_get_full("sun.sun")
    if data:
        state_str = data.get("state", "below_horizon")
        LAST_SUN_STATE = state_str
        return data
    return {"state": LAST_SUN_STATE}


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
        limit_2000 = min(round(hms_limit_target * ratio_2000), max_2000)
        limit_2000 = max(0.0, limit_2000)

    if hms_1600_online:
        limit_1600 = min(round(hms_limit_target * ratio_1600), max_1600)
        limit_1600 = max(0.0, limit_1600)

    return limit_2000, limit_1600



def safe_float(state: dict, key: str, default: float) -> float:
    """Liest State-Key sicher als float, auch wenn Wert None oder ungueltig ist."""
    val = state.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def send_telegram_alert(token, chat_id, message):
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, json=payload, timeout=5)
        if r.status_code != 200:
            log.error("Telegram Senden fehlgeschlagen: %s", r.text)
    except Exception as e:
        log.error("Telegram Fehler: %s", e)


def calc_adaptive_gs_delta(error, ki_min=0.15, ki_max=0.5, ki_error_scale=600.0):
    # Exponent 0.7 bewirkt progressiven Anstieg bei mittleren Fehlern
    ki_err_factor = min(1.0, (abs(error) / ki_error_scale) ** 0.7)
    ki_eff = ki_min + (ki_max - ki_min) * ki_err_factor
    delta = error * ki_eff
    
    # Slew-Rate-Begrenzung: sanft bei kleinem Fehler, schnell bei großem Fehler
    slew_limit = 80.0 if abs(error) < 150.0 else 250.0
    return max(-slew_limit, min(slew_limit, delta))


def set_active_mode(state, new_mode, hold_seconds=30.0):
    state["active_mode"] = new_mode
    
    # Bestimme die übergeordnete Kategorie
    if new_mode in ["active", "feed_in", "feed_in_standby"]:
        major_mode = "REGULATION"
    elif new_mode == "night":
        major_mode = "NIGHT"
    elif new_mode == "bypass":
        major_mode = "BYPASS"
    elif new_mode == "calibration":
        major_mode = "CALIBRATION"
    else:
        major_mode = new_mode
        
    old_major_mode = state.get("last_major_mode")
    if old_major_mode != major_mode:
        state["last_major_mode"] = major_mode
        if old_major_mode is not None:
            state["hold_until"] = time.monotonic() + hold_seconds
            log.info("Betriebsmodus-Kategorie geändert: %s -> %s. Hold-Time für %.0fs aktiv.", 
                     old_major_mode, major_mode, hold_seconds)


# ---------------------------------------------------------------------------
# Hauptregelschleife
# ---------------------------------------------------------------------------
def main():
    global DRY_RUN
    log.info("SunEnergy XT Controller v2.5.7 startet...")
    signal.signal(signal.SIGTERM, _handle_term)
    signal.signal(signal.SIGINT, _handle_term)
    opts  = load_options()
    state = load_state()

    DRY_RUN = bool(opts.get("dry_run", True))
    if DRY_RUN:
        log.info("DRY-RUN Modus aktiv - es wird NICHTS geschrieben!")
    else:
        log.info("Aktiver Modus - Controller schreibt in HA")

    # Konfiguration
    shelly_ip       = opts["shelly_ip"]
    grid_sensor     = opts["grid_sensor"]
    soc_sensor      = opts["soc_sensor"]
    gs_entity       = opts["gs_entity"]
    mm_switch       = opts["mm_switch"]
    sa_entity       = opts["sa_entity"]
    hms_2000_entity = opts["hms_2000_entity"]
    hms_1600_entity = opts["hms_1600_entity"]
    
    # L2 Konfiguration (optional)
    sunenergy_ip_l2 = opts.get("sunenergy_ip_l2", "")
    soc_sensor_l2   = opts.get("soc_sensor_l2", "")
    gs_entity_l2    = opts.get("gs_entity_l2", "")
    mm_switch_l2    = opts.get("mm_switch_l2", "")
    sa_entity_l2    = opts.get("sa_entity_l2", "")
    op_l2_sensor    = opts.get("op_l2_sensor", "")
    has_l2          = bool(sunenergy_ip_l2)
    
    # Neue konfigurierbare Sensoren
    haus_power_sensor     = opts.get("haus_power_sensor", "sensor.hausverbrauch_aktuell")
    hms_2000_power_sensor = opts.get("hms_2000_power_sensor", "sensor.hoymiles_hms_2000_4t_power")
    hms_1600_power_sensor = opts.get("hms_1600_power_sensor", "sensor.hoymiles_hms_1600_4t_power")
    hms_2000_reachable_sensor = opts.get("hms_2000_reachable_sensor", "binary_sensor.hoymiles_hms_2000_4t_reachable")
    hms_1600_reachable_sensor = opts.get("hms_1600_reachable_sensor", "binary_sensor.hoymiles_hms_1600_4t_reachable")
    
    telegram_token        = opts.get("telegram_token", "")
    telegram_chat_id      = opts.get("telegram_chat_id", "")

    soc_normal_max  = float(opts["soc_normal_max"])    # 95%
    soc_min         = float(opts["soc_min"])            # 10%
    calib_days      = float(opts["calibration_days"])  # 15
    sunenergy_ip    = opts.get("sunenergy_ip", "192.168.178.94")
    
    # SA auf Normalwert setzen beim Start
    ha_set_number(sa_entity, soc_normal_max)
    sunenergy_write(sunenergy_ip, {"SA": int(soc_normal_max)})
    if has_l2 and sa_entity_l2:
        ha_set_number(sa_entity_l2, soc_normal_max)
        sunenergy_write(sunenergy_ip_l2, {"SA": int(soc_normal_max)})

    use_native_pid = bool(opts.get("use_native_pid", False))
    if use_native_pid:
        ha_ip = opts.get("ha_ip", "192.168.178.132")
        md_payload = {
            "mode": "direct",
            "direct": {"dat_url": f"http://{ha_ip}:8765/meter"},
            "dat_str": {"pwr": "total_act_power"}
        }
        md_str = json.dumps(md_payload)
        log.info("Schreibe Zähler-Bindung (MD) für natives Polling...")
        sunenergy_write(sunenergy_ip, {"MD": md_str, "MM": 1})
        if has_l2:
            sunenergy_write(sunenergy_ip_l2, {"MD": md_str, "MM": 1})
        state["in_fallback_mode"] = False
        state["consecutive_polls_l1"] = 0
        state["consecutive_polls_l2"] = 0

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
    if "l2_charge_blocked" not in state:
        state["l2_charge_blocked"] = True

    # Fix #4: Device-State explizit auf None setzen damit der erste Tick
    # immer schreibt (None != jeder Wert → Write-Bedingung immer True)
    state["last_device_gs"] = None
    state["last_device_mm"] = None
    state["last_device_is"] = None
    state["last_device_gs_l2"] = None
    state["last_device_mm_l2"] = None
    state["last_device_is_l2"] = None
    state["last_gs_written_l2"] = None

    set_active_mode(state, "night")
    save_state(state)
    log.info("Addon gestartet, SA=%s%%, HMS-Limit=%sW, Speicher L2 aktiv: %s, Natives Polling: %s", 
             soc_normal_max, state["last_hms_limit"], "Ja" if has_l2 else "Nein", "Ja" if use_native_pid else "Nein")

    # Lokaler Cache für SunEnergyXT Daten zur Entlastung bei API-Ausfällen (Option C)
    op_current = 0.0
    pv_current = safe_float(state, "pv_last", 0.0)
    pb_current = 0.0
    iw_current = 0.0
    
    op_l2 = 0.0
    pv_l2 = 0.0
    pb_l2 = 0.0
    iw_l2 = 0.0

    while RUNNING:
        try:
            tick_start = time.monotonic()
            p_transfer = safe_float(state, "last_p_transfer", 0.0)

            # Merge proxy poll updates from proxy state
            proxy_state = load_proxy_state()
            for k in ["last_poll_l1_ts", "last_poll_l2_ts", "consecutive_polls_l1", "consecutive_polls_l2"]:
                if k in proxy_state:
                    state[k] = proxy_state[k]

            is_native = use_native_pid and not state.get("in_fallback_mode", False)

            # ------------------------------------------------------------------
            # 1. Messwerte lesen
            # ------------------------------------------------------------------
            read_direct = False
            if use_native_pid:
                direct_p = shelly_direct_power(shelly_ip)
                if direct_p is not None:
                    grid_p_raw = direct_p
                    read_direct = True

            if not read_direct:
                grid_val = ha_get_state(grid_sensor)
                if grid_val not in (None, "unknown", "unavailable"):
                    grid_p_raw = float(grid_val)
                else:
                    grid_p_raw = safe_float(state, "grid_p_filtered", 0.0)
                    log.warning("Grid-Sensor (%s) offline — verwende letzten Wert %.0fW", grid_sensor, grid_p_raw)

            soc_val = ha_get_state(soc_sensor)
            if soc_val not in (None, "unknown", "unavailable"):
                curr_soc = float(soc_val)
                state["soc"] = curr_soc
            else:
                curr_soc = safe_float(state, "soc", 0.0)
                log.warning("SOC-Sensor (%s) offline — verwende letzten Wert %.0f%%", soc_sensor, curr_soc)

            # L2 SOC einlesen
            curr_soc_l2 = 0.0
            if has_l2 and soc_sensor_l2:
                soc_val_l2 = ha_get_state(soc_sensor_l2)
                if soc_val_l2 not in (None, "unknown", "unavailable"):
                    curr_soc_l2 = float(soc_val_l2)
                    state["soc_l2"] = curr_soc_l2
                else:
                    curr_soc_l2 = safe_float(state, "soc_l2", 0.0)
                    log.warning("L2 SOC-Sensor (%s) offline — verwende letzten Wert %.0f%%", soc_sensor_l2, curr_soc_l2)

            # Hysteresis für niedrigen SOC (Entladeschutz) L1
            low_soc_active_l1 = state.get("low_soc_active_l1", False)
            if curr_soc <= soc_min:
                low_soc_active_l1 = True
            elif curr_soc >= (soc_min + 2.0):
                low_soc_active_l1 = False
            state["low_soc_active_l1"] = low_soc_active_l1

            # Hysteresis für niedrigen SOC (Entladeschutz) L2
            low_soc_active_l2 = state.get("low_soc_active_l2", False)
            if has_l2:
                if curr_soc_l2 <= soc_min:
                    low_soc_active_l2 = True
                elif curr_soc_l2 >= (soc_min + 2.0):
                    low_soc_active_l2 = False
            else:
                low_soc_active_l2 = True
            state["low_soc_active_l2"] = low_soc_active_l2

            # Globaler Entladeschutz aktiv wenn ALLE aktiven Speicher leer sind
            low_soc_active = low_soc_active_l1 and low_soc_active_l2
            state["low_soc_active"] = low_soc_active
            
            # v2.1.5: Entlade-Aktivität für den Proxy signalisieren (Entkopplung von PV-Drossel)
            state["discharge_active_l1"] = not low_soc_active_l1
            state["discharge_active_l2"] = not low_soc_active_l2 if has_l2 else False

            solar_2000_val = ha_get_state(hms_2000_power_sensor)
            if solar_2000_val not in (None, "unknown", "unavailable"):
                solar_p_2000 = abs(float(solar_2000_val))
                hms_2000_online = True
            else:
                solar_p_2000 = safe_float(state, "solar_p_2000_last", 0.0)
                hms_2000_online = (ha_get_state(hms_2000_reachable_sensor, "off") == "on")
                if not hms_2000_online:
                    solar_p_2000 = 0.0
                log.debug("HMS-2000 Power-Sensor offline — online: %s, val: %.0fW", hms_2000_online, solar_p_2000)

            solar_1600_val = ha_get_state(hms_1600_power_sensor)
            if solar_1600_val not in (None, "unknown", "unavailable"):
                solar_p_1600 = abs(float(solar_1600_val))
                hms_1600_online = True
            else:
                solar_p_1600 = safe_float(state, "solar_p_1600_last", 0.0)
                hms_1600_online = (ha_get_state(hms_1600_reachable_sensor, "off") == "on")
                if not hms_1600_online:
                    solar_p_1600 = 0.0
                log.debug("HMS-1600 Power-Sensor offline — online: %s, val: %.0fW", hms_1600_online, solar_p_1600)
            
            solar_p = (solar_p_2000 if hms_2000_online else 0) + (solar_p_1600 if hms_1600_online else 0)

            # Plausibilitätsfilter für solar_p Aussetzer (max. 3 Ticks / 15s überbrücken)
            last_solar_p = state.get("last_solar_p", solar_p)
            solar_p_dropouts = state.get("solar_p_dropouts", 0)

            if solar_p < 10.0 and last_solar_p > 200.0:
                if solar_p_dropouts < 3:
                    log.warning("⚠️ solar_p Aussetzer (%.0fW -> %.0fW), verwende letzten Wert (Tick %d/3)", 
                                solar_p, last_solar_p, solar_p_dropouts + 1)
                    solar_p = last_solar_p
                    state["solar_p_dropouts"] = solar_p_dropouts + 1
                else:
                    log.warning("⚠️ solar_p dauerhaft niedrig (3 Ticks), akzeptiere Wert (%.0fW)", solar_p)
                    state["solar_p_dropouts"] = 0
            else:
                state["solar_p_dropouts"] = 0

            state["last_solar_p"] = solar_p

            # Watchdog
            watchdog_ok = False
            if read_direct:
                watchdog_ok = True
            else:
                shelly_data = ha_get_full(grid_sensor)
                if shelly_data:
                    last_upd = shelly_data.get("last_updated", "")
                    try:
                        upd_ts = datetime.fromisoformat(last_upd.replace("Z", "+00:00")).timestamp()
                        watchdog_ok = (time.time() - upd_ts) < 60
                    except Exception:
                        watchdog_ok = False

            # ------------------------------------------------------------------
            # 2. Sicherheits-Stopp (v1.9.2: erst Shelly-Direkt-Fallback versuchen)
            # ------------------------------------------------------------------
            if not watchdog_ok:
                direct_p = shelly_direct_power(shelly_ip)
                if direct_p is not None:
                    grid_p_raw = direct_p
                    watchdog_ok = True
                    log.warning("HA-API/Grid-Sensor stale — Grid direkt vom Shelly gelesen: %.0fW", direct_p)

            if not watchdog_ok:
                log.warning("Watchdog Fehler! Grid-Sensor UND Shelly-Direktzugriff offline — Sicherheits-Stopp (IS=10, MM=1).")
                ha_switch(mm_switch, True)
                ha_set_number(gs_entity, 0)
                sunenergy_write(sunenergy_ip, {"IS": 10, "MM": 1, "GS": 0})
                state["last_device_gs"] = None
                state["last_device_mm"] = None
                state["last_device_is"] = None
                state["last_gs_written"] = None
                
                if has_l2 and mm_switch_l2 and gs_entity_l2:
                    ha_switch(mm_switch_l2, True)
                    ha_set_number(gs_entity_l2, 0)
                    sunenergy_write(sunenergy_ip_l2, {"IS": 10, "MM": 1, "GS": 0})
                    state["last_device_gs_l2"] = None
                    state["last_device_mm_l2"] = None
                    state["last_device_is_l2"] = None
                    state["last_gs_written_l2"] = None
                    
                save_state(state)
                sleep_tick(TICK_S)
                continue

            # ------------------------------------------------------------------
            # 3. SunEnergyXT Status lesen (OP = aktueller AC-Ausgang)
            # ------------------------------------------------------------------
            # L1 Speicher lesen
            prev_l1_ok = state.get("l1_polling_ok", True)
            prev_l2_ok = state.get("l2_polling_ok", True)

            se_data = sunenergy_read(sunenergy_ip)
            if se_data:
                op_current = float(se_data.get("OP", 0))
                pv_current = float(se_data.get("PV", 0))
                pb_current = float(se_data.get("BP", 0))
                iw_current = float(se_data.get("IW", 0))
                state["l1_polling_ok"] = True
                state["last_poll_l1_ts"] = time.time()
                state["consecutive_polls_l1"] = state.get("consecutive_polls_l1", 0) + 1
                
                # MM Self-healing
                mm_val = se_data.get("MM")
                target_mm = 1 if is_native else 0
                if mm_val is not None and str(mm_val) != str(target_mm):
                    log.warning("L1 MM state mismatch: reported=%s, target=%s. Enforcing...", mm_val, target_mm)
                    if target_mm == 1:
                        ha_ip = opts.get("ha_ip", "192.168.178.132")
                        md_payload = {
                            "mode": "direct",
                            "direct": {"dat_url": f"http://{ha_ip}:8765/meter"},
                            "dat_str": {"pwr": "total_act_power"}
                        }
                        md_str = json.dumps(md_payload)
                        sunenergy_write(sunenergy_ip, {"MD": md_str, "MM": 1, "GS": 0})
                    else:
                        sunenergy_write(sunenergy_ip, {"MM": 0})
                    state["last_device_mm"] = target_mm
                    state["last_device_is"] = state.get("last_device_is") or 2400
                    state["last_device_gs"] = state.get("last_device_gs") or 0
            else:
                state["l1_polling_ok"] = False
                state["consecutive_polls_l1"] = 0
                log.warning("SunEnergyXT L1 API nicht erreichbar, verwende letzte Werte (OP=%.1fW, PV=%.1fW, BP=%.1fW)", 
                            op_current, pv_current, pb_current)
            
            state["soc"] = curr_soc
            state["pv_last"] = pv_current

            # L2 Speicher lesen
            op_l2 = 0.0
            pv_l2 = 0.0
            pb_l2 = 0.0
            iw_l2 = 0.0
            se_data_l2 = None
            if has_l2:
                se_data_l2 = sunenergy_read(sunenergy_ip_l2)
                if se_data_l2:
                    op_l2 = float(se_data_l2.get("OP", 0))
                    pv_l2 = float(se_data_l2.get("PV", 0))
                    pb_l2 = float(se_data_l2.get("BP", 0))
                    iw_l2 = float(se_data_l2.get("IW", 0))
                    state["pv_last_l2"] = pv_l2
                    state["l2_polling_ok"] = True
                    state["last_poll_l2_ts"] = time.time()
                    state["consecutive_polls_l2"] = state.get("consecutive_polls_l2", 0) + 1
                    
                    # v2.5.1: L2 Lade-Blockade-Erkennung (BMS voll, App-Limit oder unplugged)
                    last_gs_l2 = safe_float(state, "last_device_gs_l2", 0.0)
                    if last_gs_l2 < -100.0:
                        if iw_l2 < 50.0:
                            if not state.get("l2_charge_blocked", False):
                                log.warning("⚠️ L2 lädt nicht: angefordert=%.0fW, bezogen=%.1fW. Blockiere L2 Ladekapazität gegen Einspeise-Deadlock.", last_gs_l2, iw_l2)
                            state["l2_charge_blocked"] = True
                        else:
                            state["l2_charge_blocked"] = False
                    else:
                        limit_val = float(state.get("last_written_sa") or soc_normal_max)
                        if curr_soc_l2 < (limit_val - 1.0):
                            state["l2_charge_blocked"] = False
                        else:
                            state["l2_charge_blocked"] = True

                    # MM Self-healing
                    mm_val_l2 = se_data_l2.get("MM")
                    target_mm_l2 = 1 if is_native else 0
                    if mm_val_l2 is not None and str(mm_val_l2) != str(target_mm_l2):
                        log.warning("L2 MM state mismatch: reported=%s, target=%s. Enforcing...", mm_val_l2, target_mm_l2)
                        if target_mm_l2 == 1:
                            ha_ip = opts.get("ha_ip", "192.168.178.132")
                            md_payload = {
                                "mode": "direct",
                                "direct": {"dat_url": f"http://{ha_ip}:8765/meter"},
                                "dat_str": {"pwr": "total_act_power"}
                            }
                            md_str = json.dumps(md_payload)
                            sunenergy_write(sunenergy_ip_l2, {"MD": md_str, "MM": 1, "GS": 0})
                        else:
                            sunenergy_write(sunenergy_ip_l2, {"MM": 0})
                        state["last_device_mm_l2"] = target_mm_l2
                        state["last_device_is_l2"] = state.get("last_device_is_l2") or 2400
                        state["last_device_gs_l2"] = state.get("last_device_gs_l2") or 0
                else:
                    pv_l2 = safe_float(state, "pv_last_l2", 0.0)
                    state["l2_polling_ok"] = False
                    state["consecutive_polls_l2"] = 0
                    log.warning("SunEnergyXT L2 API nicht erreichbar, verwende letzte Werte (OP=%.1fW, PV=%.1fW, BP=%.1fW)", 
                                op_l2, pv_l2, pb_l2)

                # v2.2.5: Optionale Entladeleistung von L2 via HA-Sensor überschreiben, falls konfiguriert
                # Negative Werte des Shelly (Einspeisung/Entladung) werden als positive OP-Leistung interpretiert.
                if op_l2_sensor:
                    op_l2_val = ha_get_state(op_l2_sensor)
                    if op_l2_val is not None:
                        try:
                            val = float(op_l2_val)
                            op_l2 = -val if val < 0 else 0.0
                        except ValueError:
                            log.error("Konnte L2-Leistungssensor %s nicht als float parsen: %s", op_l2_sensor, op_l2_val)
            else:
                state["l2_polling_ok"] = True

            # Sofort speichern, falls sich der Online-Status geändert hat
            if state.get("l1_polling_ok", True) != prev_l1_ok or state.get("l2_polling_ok", True) != prev_l2_ok:
                save_state(state)

            # Integrator-Reset bei plötzlichem OP-Einbruch auf 0
            # Verhindert Windup wenn die Batterie kurz abschaltet und dann mit falschem GS wiederkommt
            prev_op_l1 = safe_float(state, "op_l1", op_current)
            prev_op_l2 = safe_float(state, "op_l2", op_l2)
            if prev_op_l1 > 100.0 and op_current < 10.0:
                log.warning("L1 OP-Einbruch erkannt (%.0fW -> %.0fW) — setze GS-Integrator zurueck", prev_op_l1, op_current)
                state["last_gs"] = 0.0
            if has_l2 and prev_op_l2 > 100.0 and op_l2 < 10.0:
                log.warning("L2 OP-Einbruch erkannt (%.0fW -> %.0fW) — setze GS-Integrator zurueck", prev_op_l2, op_l2)

            # Speicher-Leistungswerte im Zustand sichern
            state["op_l1"] = op_current
            state["pv_l1"] = pv_current
            state["iw_l1"] = iw_current
            state["pb_l1"] = pb_current
            
            state["op_l2"] = op_l2
            state["pv_l2"] = pv_l2
            state["iw_l2"] = iw_l2
            state["pb_l2"] = pb_l2

            # --- PV-Eingangs-Überwachung (MPPT-Watchdog) ---
            if "active_inputs" not in state:
                state["active_inputs"] = {"L1": {}, "L2": {}}
            if "sent_alerts" not in state:
                state["sent_alerts"] = {}
            if "pv_drop_ticks" not in state:
                state["pv_drop_ticks"] = {}

            def monitor_device_pvs(device_name, se_dict, total_pv):
                if not se_dict:
                    return
                # 1. Prüfen, welche Ports aktiv sind
                for i in range(1, 5):
                    vp_val = safe_float(se_dict, f"VP{i}", 0.0)
                    pv_val = safe_float(se_dict, f"PV{i}", 0.0)
                    if vp_val > 10.0 or pv_val > 0.0:
                        if not state["active_inputs"][device_name].get(str(i)):
                            state["active_inputs"][device_name][str(i)] = True
                            log.info("PV-Watchdog: Port PV%d bei %s als aktiv markiert (Spannung vorhanden).", i, device_name)

                # 2. Watchdog-Überwachung (nur wenn das Gerät insgesamt > 150W produziert und somit Tageslicht herrscht)
                if total_pv > 150.0:
                    for i in range(1, 5):
                        if state["active_inputs"][device_name].get(str(i)):
                            vp_val = safe_float(se_dict, f"VP{i}", 0.0)
                            pv_val = safe_float(se_dict, f"PV{i}", 0.0)
                            
                            # Wenn Spannung und Leistung komplett auf 0 abfallen
                            if vp_val == 0.0 and pv_val == 0.0:
                                tick_key = f"{device_name}_PV{i}"
                                current_ticks = state["pv_drop_ticks"].get(tick_key, 0) + 1
                                state["pv_drop_ticks"][tick_key] = current_ticks
                                
                                # Nach 5 Minuten (60 Ticks bei 5s Intervall) Warnung senden
                                if current_ticks == 60:
                                    alert_key = f"pv_drop_{device_name}_PV{i}"
                                    if alert_key not in state["sent_alerts"]:
                                        alert_msg = (
                                            f"⚠️ <b>SunEnergy XT Controller Alarm!</b>\n"
                                            f"Der Solar-Eingang <b>PV{i}</b> am Gerät <b>{device_name}</b> liefert keine Spannung mehr (0.0V), "
                                            f"obwohl der Speicher insgesamt {total_pv:.0f}W PV-Leistung erzeugt.\n"
                                            f"Bitte Sicherungen, Stecker und Kabel überprüfen!"
                                        )
                                        send_telegram_alert(telegram_token, telegram_chat_id, alert_msg)
                                        state["sent_alerts"][alert_key] = time.time()
                                        log.warning("PV-Watchdog: Telegram-Alarm gesendet für %s Port PV%d (Spannungsverlust).", device_name, i)
                            else:
                                tick_key = f"{device_name}_PV{i}"
                                state["pv_drop_ticks"][tick_key] = 0
                                
                                alert_key = f"pv_drop_{device_name}_PV{i}"
                                if alert_key in state["sent_alerts"]:
                                    recovery_msg = (
                                        f"🟢 <b>SunEnergy XT Controller Entwarnung.</b>\n"
                                        f"Der Solar-Eingang <b>PV{i}</b> am Gerät <b>{device_name}</b> liefert wieder Spannung (aktuell {vp_val:.1f}V)."
                                    )
                                    send_telegram_alert(telegram_token, telegram_chat_id, recovery_msg)
                                    del state["sent_alerts"][alert_key]
                                    log.info("PV-Watchdog: Entwarnung gesendet für %s Port PV%d.", device_name, i)

            monitor_device_pvs("L1", se_data, pv_current)
            if has_l2 and se_data_l2:
                monitor_device_pvs("L2", se_data_l2, pv_l2)



            # Berechne den Hausverbrauch lokal und verzögerungsfrei
            SE_CHARGER_EFF = 0.9
            
            # L1 AC-Leistung schätzen
            if op_current > 5.0:
                battery_ac_est_l1 = op_current
            else:
                dc_from_ac_l1 = max(0.0, pb_current - pv_current)
                battery_ac_est_l1 = -(dc_from_ac_l1 / SE_CHARGER_EFF)

            # L2 AC-Leistung schätzen
            if op_l2 > 5.0:
                battery_ac_est_l2 = op_l2
            else:
                dc_from_ac_l2 = max(0.0, pb_l2 - pv_l2)
                battery_ac_est_l2 = -(dc_from_ac_l2 / SE_CHARGER_EFF)

            # Gesamt-Batterieleistung
            battery_ac_est = battery_ac_est_l1 + battery_ac_est_l2
            haus_p = max(0.0, grid_p_raw + solar_p + battery_ac_est)

            # Plausibilitätsfilter für haus_p Aussetzer (max. 3 Ticks / 15s überbrücken)
            last_haus_p = state.get("last_haus_p", haus_p)
            haus_p_dropouts = state.get("haus_p_dropouts", 0)

            if haus_p < 50.0 and last_haus_p > 200.0:
                if haus_p_dropouts < 3:
                    log.warning("⚠️ haus_p Aussetzer (%.0fW -> %.0fW), verwende letzten Wert (Tick %d/3)", 
                                haus_p, last_haus_p, haus_p_dropouts + 1)
                    haus_p = last_haus_p
                    state["haus_p_dropouts"] = haus_p_dropouts + 1
                else:
                    log.warning("⚠️ haus_p dauerhaft niedrig (3 Ticks), akzeptiere Wert (%.0fW)", haus_p)
                    state["haus_p_dropouts"] = 0
            else:
                state["haus_p_dropouts"] = 0

            state["last_haus_p"] = haus_p

            # AC-AC Kreuzladungs-Erkennung und direktes Speichern für schnelles Proxy-Breakout
            # Deaktiviert während der gewollten SOC-Angleichung (p_transfer > 10W)
            ac_charge_l1 = max(0.0, iw_current - pv_current)
            ac_charge_l2 = max(0.0, iw_l2 - pv_l2)
            
            # Kreuzladung liegt nur vor, wenn der abgebende Akku NETTO aus seinen Zellen entlädt
            l1_entlaedt_netto = (op_current - pv_current) > 100.0
            l2_entlaedt_netto = (op_l2 - pv_l2) > 100.0
            
            if p_transfer <= 10.0 and ((ac_charge_l1 > 100.0 and l2_entlaedt_netto) or (ac_charge_l2 > 100.0 and l1_entlaedt_netto)):
                log.warning("⚠️ AC-AC Kreuzladung erkannt (L1_AC_charge=%.0fW, L2_AC_charge=%.0fW, L1_OP=%.0fW, L2_OP=%.0fW)! Sofortkorrektur!",
                            ac_charge_l1, ac_charge_l2, op_current, op_l2)
                
                # Hold-Time setzen damit der Regler nicht sofort wieder aufmacht
                state["kreuzladung_hold_until"] = time.time() + 30  # 30s warten
                
                # Direkt schreiben, nicht auf nächsten Zyklus warten
                sunenergy_write(sunenergy_ip, {"GS": 0, "IS": max(200, int(haus_p))})
                if has_l2:
                    sunenergy_write(sunenergy_ip_l2, {"GS": 0, "IS": max(200, int(haus_p))})
                
                # State synchronisieren
                state["last_device_gs"] = 0
                state["last_device_gs_l2"] = 0
                state["last_device_is"] = max(200, int(haus_p))
                if has_l2:
                    state["last_device_is_l2"] = max(200, int(haus_p))
                
                save_state(state)

            # Fallback-Überwachung für use_native_pid
            if use_native_pid:
                l1_poll_age = time.time() - state.get("last_poll_l1_ts", 0)
                l2_poll_age = time.time() - state.get("last_poll_l2_ts", 0)
                
                l1_stale = l1_poll_age > 15
                l2_stale = has_l2 and l2_poll_age > 15
                
                l1_failed = not state.get("l1_polling_ok", True)
                l2_failed = has_l2 and not state.get("l2_polling_ok", True)
                
                needs_fallback = l1_stale or l2_stale or l1_failed or l2_failed
                in_fallback = state.get("in_fallback_mode", False)
                
                if needs_fallback:
                    if not in_fallback:
                        log.warning("⚠️ Fallback auslösen! Grund: "
                                    f"L1_stale={l1_stale} L2_stale={l2_stale} "
                                    f"L1_failed={l1_failed} L2_failed={l2_failed}")
                        state["in_fallback_mode"] = True
                        state["consecutive_polls_l1"] = 0
                        state["consecutive_polls_l2"] = 0
                        send_telegram_alert(
                            telegram_token,
                            telegram_chat_id,
                            f"⚠️ <b>SunEnergy XT Controller: Fallback-Modus aktiv!</b>\n"
                            f"Grund: Verbindungsausfall oder veraltete Werte bei:\n"
                            f"- L1_stale: {l1_stale}, L2_stale: {l2_stale}\n"
                            f"- L1_failed: {l1_failed}, L2_failed: {l2_failed}"
                        )
                        
                        # Sofort auf MM=0 schalten, um manuelle Kontrolle zu erzwingen
                        ha_switch(mm_switch, False)
                        if has_l2 and mm_switch_l2:
                            ha_switch(mm_switch_l2, False)
                        sunenergy_write(sunenergy_ip, {"MM": 0})
                        if has_l2:
                            sunenergy_write(sunenergy_ip_l2, {"MM": 0})
                            
                        state["last_device_mm"] = None
                        state["last_device_mm_l2"] = None
                        save_state(state)
                else:
                    polls_ok_l1 = state.get("consecutive_polls_l1", 0) >= 3
                    polls_ok_l2 = not has_l2 or state.get("consecutive_polls_l2", 0) >= 3
                    
                    if in_fallback and polls_ok_l1 and polls_ok_l2:
                        log.info("🟢 Rückkehr zum nativen PID-Modus. Hysterese-Polls ok (L1=%d, L2=%d).",
                                 state.get("consecutive_polls_l1", 0), state.get("consecutive_polls_l2", 0))
                        state["in_fallback_mode"] = False
                        send_telegram_alert(
                            telegram_token,
                            telegram_chat_id,
                            "🟢 <b>SunEnergy XT Controller: Fallback beendet.</b>\n"
                            "Die Regelung läuft wieder normal im aktiven Modus."
                        )
                        
                        # Wieder Zählerbindung und MM=1 schreiben
                        ha_ip = opts.get("ha_ip", "192.168.178.132")
                        md_payload = {
                            "mode": "direct",
                            "direct": {"dat_url": f"http://{ha_ip}:8765/meter"},
                            "dat_str": {"pwr": "total_act_power"}
                        }
                        md_str = json.dumps(md_payload)
                        
                        sunenergy_write(sunenergy_ip, {"MD": md_str, "MM": 1, "GS": 0})
                        if has_l2:
                            sunenergy_write(sunenergy_ip_l2, {"MD": md_str, "MM": 1, "GS": 0})
                            
                        state["last_device_gs"] = None
                        state["last_device_mm"] = None
                        state["last_device_gs_l2"] = None
                        state["last_device_mm_l2"] = None
                        save_state(state)
            else:
                state["in_fallback_mode"] = False

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

                # Überschuss-Bedingung: Gesamte Erzeugung (Hoymiles + beide Speicher PV) übersteigt Hausverbrauch
                surplus = (solar_p + pv_current + pv_l2) - haus_p
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
                        HA_SESSION.post(
                            f"{HA_URL}/api/services/input_boolean/turn_off",
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
            # 3c. Bypass Nulleinspeisung prüfen (Sofortiger und dauerhafter Bypass)
            # ------------------------------------------------------------------
            bypass_tomorrow_switch = opts.get("bypass_tomorrow_switch", "input_boolean.sunenergy_bypass_tomorrow")
            bypass_active = False
            if bypass_tomorrow_switch:
                bypass_switch_state = ha_get_state(bypass_tomorrow_switch, "off")
                if bypass_switch_state == "on":
                    if not state.get("bypass_active_logged", False):
                        log.info("⚡ Nulleinspeisung-Bypass SOFORT AKTIV (dauerhaft bis zum manuellen Ausschalten).")
                        state["bypass_active_logged"] = True
                        save_state(state)
                    bypass_active = True
                else:
                    if state.get("bypass_active_logged", False):
                        log.info("⚡ Nulleinspeisung-Bypass DEAKTIVIERT (zurück zur Nulleinspeisung).")
                        state["bypass_active_logged"] = False
                        save_state(state)


            # ------------------------------------------------------------------
            # 4. Sonnenstand
            # ------------------------------------------------------------------
            sun_above = get_sun_state().get("state") == "above_horizon"

            # ------------------------------------------------------------------
            # 5. Zwangsladung prüfen und Ladelimit (SA) anpassen
            # ------------------------------------------------------------------
            tage_seit = (time.time() - state["last_calibration_ts"]) / 86400
            
            # Kalibrierungs-Fälligkeit prüfen (Ziel: 10:00 Uhr des Ziel-Tages)
            try:
                last_cal_dt = datetime.fromtimestamp(state["last_calibration_ts"])
                target_dt = last_cal_dt + timedelta(days=calib_days)
                target_10am = target_dt.replace(hour=10, minute=0, second=0, microsecond=0)
                calibration_due = datetime.now() >= target_10am
            except Exception as e:
                log.error("Fehler bei Kalibrierungszeit-Berechnung: %s", e)
                calibration_due = tage_seit > calib_days

            # Kalibrierungs-Ladelimit bestimmen: 100% wenn fällig (erlaubt solares Laden), sonst soc_normal_max
            target_sa = 100 if calibration_due else soc_normal_max
            if state.get("last_written_sa") != target_sa:
                log.info("Setze Ladelimit SA auf %d%% (Kalibrierung fällig: %s)", target_sa, "Ja" if calibration_due else "Nein")
                ha_set_number(sa_entity, target_sa)
                sunenergy_write(sunenergy_ip, {"SA": int(target_sa)})
                state["last_written_sa"] = target_sa
                save_state(state)

            # Verwende target_sa (100 oder 95) als dynamische SOC-Grenze in der Regelung
            soc_max_limit = float(target_sa)

            zwangsladung_trigger = (
                calibration_due
                and not sun_above
                and (curr_soc < 100 or (has_l2 and curr_soc_l2 < 100))
                and state["active_mode"] != "calibration"
            )
            if zwangsladung_trigger:
                log.info("Zwangsladung gestartet! %.1f Tage seit letzter Vollladung", tage_seit)
                set_active_mode(state, "calibration")
                save_state(state)

            if state["active_mode"] == "calibration" and (curr_soc < 100 or (has_l2 and curr_soc_l2 < 100)):
                log.info("Zwangsladung läuft... SOC_L1=%.1f%% SOC_L2=%.1f%%", curr_soc, curr_soc_l2)
                # v1.9.2: Spam-Schutz — nur beim Eintritt/nach Drift schreiben,
                # nicht jeden Tick (HA + Geräte-Flash schonen)
                if state.get("last_device_gs") != -2400 or state.get("last_device_mm") != 0:
                    ha_set_number(sa_entity, 100)
                    ha_switch(mm_switch, False)
                    ha_set_number(gs_entity, -2400)
                    sunenergy_write(sunenergy_ip, {"GS": -2400, "MM": 0})
                    state["last_device_gs"] = -2400
                    state["last_device_mm"] = 0
                    state["last_gs_written"] = -2400
                    save_state(state)
                if has_l2:
                    if state.get("last_device_gs_l2") != -2400 or state.get("last_device_mm_l2") != 0:
                        if sa_entity_l2:
                            ha_set_number(sa_entity_l2, 100)
                        if mm_switch_l2:
                            ha_switch(mm_switch_l2, False)
                        if gs_entity_l2:
                            ha_set_number(gs_entity_l2, -2400)
                        sunenergy_write(sunenergy_ip_l2, {"GS": -2400, "MM": 0})
                        state["last_device_gs_l2"] = -2400
                        state["last_device_mm_l2"] = 0
                        state["last_gs_written_l2"] = -2400
                        save_state(state)
                sleep_tick(TICK_S)
                continue

            if state["active_mode"] == "calibration" and curr_soc >= 100 and (not has_l2 or curr_soc_l2 >= 100):
                log.info("Zwangsladung abgeschlossen!")
                state["last_calibration_ts"] = time.time()
                set_active_mode(state, "night")
                
                # L1 zurücksetzen
                ha_set_number(sa_entity, soc_normal_max)
                ha_switch(mm_switch, True)
                ha_set_number(gs_entity, 0)
                sunenergy_write(sunenergy_ip, {"SA": int(soc_normal_max), "IS": 2400, "GS": 0})
                state["last_written_sa"] = soc_normal_max
                state["last_device_gs"] = None
                state["last_device_mm"] = None
                state["last_device_is"] = None
                
                # L2 zurücksetzen
                if has_l2:
                    if sa_entity_l2:
                        ha_set_number(sa_entity_l2, soc_normal_max)
                    if mm_switch_l2:
                        ha_switch(mm_switch_l2, True)
                    if gs_entity_l2:
                        ha_set_number(gs_entity_l2, 0)
                    sunenergy_write(sunenergy_ip_l2, {"SA": int(soc_normal_max), "IS": 2400, "GS": 0})
                    state["last_device_gs_l2"] = None
                    state["last_device_mm_l2"] = None
                    state["last_device_is_l2"] = None
                
                save_state(state)
                sleep_tick(TICK_S)
                continue

            # ------------------------------------------------------------------
            # 6. Nachtmodus
            # ------------------------------------------------------------------
            if not sun_above:
                is_native = use_native_pid and not state.get("in_fallback_mode", False)

                if state["active_mode"] != "night":
                    log.info("Nachtmodus aktiv: %s", "Natives Polling" if is_native else "MM=0, aktive GS-Regelung")
                    
                    if not is_native:
                        # MM ausschalten (für manuelle Regelung über GS)
                        current_mm_state = ha_get_state(mm_switch, "on")
                        if current_mm_state != "off":
                            ha_switch(mm_switch, False)
                        if has_l2 and mm_switch_l2:
                            current_mm_state_l2 = ha_get_state(mm_switch_l2, "on")
                            if current_mm_state_l2 != "off":
                                ha_switch(mm_switch_l2, False)
                    
                    # Hoymiles auf Maximum setzen
                    ha_set_number(hms_2000_entity, 2000)
                    ha_set_number(hms_1600_entity, 1600)
                    
                    # IS auf Maximum
                    sunenergy_write(sunenergy_ip, {"IS": 2400})
                    if has_l2:
                        sunenergy_write(sunenergy_ip_l2, {"IS": 2400})
                    
                    if not is_native:
                        sunenergy_write(sunenergy_ip, {"MM": 0})
                        if has_l2:
                            sunenergy_write(sunenergy_ip_l2, {"MM": 0})
                    
                    set_active_mode(state, "night")
                    state["last_device_mm"] = 0 if not is_native else None
                    state["last_device_is"] = 2400
                    state["last_device_gs"] = None
                    if has_l2:
                        state["last_device_mm_l2"] = 0 if not is_native else None
                        state["last_device_is_l2"] = 2400
                        state["last_device_gs_l2"] = None
                    state["last_hms_2000_lim"] = 2000
                    state["last_hms_1600_lim"] = 1600
                    state["last_hms_limit"] = 3600.0

                if is_native:
                    # Im nativen Modus schreiben wir nur IS als Schutz, kein GS
                    is_target_night_l1 = 10 if low_soc_active_l1 else 2400
                    if state.get("last_device_is") != is_target_night_l1:
                        sunenergy_write(sunenergy_ip, {"IS": is_target_night_l1})
                        state["last_device_is"] = is_target_night_l1
                        
                    is_target_night_l2 = 2400
                    if has_l2:
                        is_target_night_l2 = 10 if low_soc_active_l2 else 2400
                        if state.get("last_device_is_l2") != is_target_night_l2:
                            sunenergy_write(sunenergy_ip_l2, {"IS": is_target_night_l2})
                            state["last_device_is_l2"] = is_target_night_l2
                            
                    gs_l1_rounded = 0
                    gs_l2_rounded = 0
                    gs_new_rounded = 0
                    
                    if state.get("last_gs_written") != 0:
                        ha_set_number(gs_entity, 0)
                        state["last_gs_written"] = 0
                    if has_l2 and gs_entity_l2 and state.get("last_gs_written_l2") != 0:
                        ha_set_number(gs_entity_l2, 0)
                        state["last_gs_written_l2"] = 0

                    log.info("Nacht (Nativ): IS_L1=%dW IS_L2=%dW | grid=%.0fW haus=%.0fW SOC_L1=%.0f%% SOC_L2=%.0f%%",
                             is_target_night_l1, is_target_night_l2 if has_l2 else 0, grid_p_raw, haus_p, curr_soc, curr_soc_l2)
                else:
                    # GS nachts aktiv regeln
                    max_gs = 4800.0 if has_l2 else 2400.0
                    gs_last = safe_float(state, "last_gs", 0.0)
                    _delta_night = calc_adaptive_gs_delta(grid_p_raw)
                    gs_new = gs_last + _delta_night

                    hold_until = state.get("hold_until", 0.0)
                    if time.monotonic() < hold_until:
                        gs_new = gs_last

                    # Anti-Windup bei vollen/nicht ladbaren Batterien (nachts)
                    headroom_l1 = max(0.0, soc_max_limit - curr_soc)
                    l2_charge_blocked = state.get("l2_charge_blocked", False)
                    headroom_l2 = max(0.0, soc_max_limit - curr_soc_l2) if (has_l2 and not l2_charge_blocked) else 0.0
                    total_headroom = headroom_l1 + headroom_l2
                    if total_headroom <= 0.0:
                        gs_new = max(0.0, gs_new)

                    if low_soc_active:
                        gs_new = min(0.0, gs_new)
                    gs_new = max(-max_gs, min(max_gs, gs_new))

                    # Aufteilung auf L1 und L2
                    gs_l1 = 0.0
                    gs_l2 = 0.0
                    if gs_new > 0:
                        # Entladen proportional zum SOC
                        usable_soc_l1 = max(0.0, curr_soc - soc_min) if not low_soc_active_l1 else 0.0
                        usable_soc_l2 = max(0.0, curr_soc_l2 - soc_min) if (has_l2 and not low_soc_active_l2) else 0.0
                        total_usable = usable_soc_l1 + usable_soc_l2
                        if total_usable > 0:
                            ratio_l1 = usable_soc_l1 / total_usable
                            ratio_l2 = usable_soc_l2 / total_usable
                            gs_l1 = gs_new * ratio_l1
                            gs_l2 = gs_new * ratio_l2
                            if gs_l1 > 2400:
                                rem = gs_l1 - 2400
                                gs_l1 = 2400
                                if usable_soc_l2 > 0.0:
                                    gs_l2 = min(2400, gs_l2 + rem)
                            elif gs_l2 > 2400:
                                rem = gs_l2 - 2400
                                gs_l2 = 2400
                                if usable_soc_l1 > 0.0:
                                    gs_l1 = min(2400, gs_l1 + rem)
                    elif gs_new < 0:
                        # Laden proportional zum Headroom
                        if total_headroom > 0:
                            ratio_l1 = headroom_l1 / total_headroom
                            ratio_l2 = headroom_l2 / total_headroom
                            gs_l1 = gs_new * ratio_l1
                            gs_l2 = gs_new * ratio_l2
                            if gs_l1 < -2400:
                                rem = gs_l1 + 2400
                                gs_l1 = -2400
                                if headroom_l2 > 0.0:
                                    gs_l2 = max(-2400, gs_l2 + rem)
                            elif gs_l2 < -2400:
                                rem = gs_l2 + 2400
                                gs_l2 = -2400
                                if headroom_l1 > 0.0:
                                    gs_l1 = max(-2400, gs_l1 + rem)

                    # Kreuzladung Hold-Time aktiv? Dann Laden (negatives GS) verhindern
                    if time.time() < state.get("kreuzladung_hold_until", 0):
                        gs_l1 = max(0.0, gs_l1)
                        gs_l2 = max(0.0, gs_l2)
                        log.debug("Kreuzladung Hold-Time aktiv (Nacht) — Laden (negatives GS) gesperrt")

                    # Sicherheitsgrenzen bei niedrigem SOC anwenden
                    if low_soc_active_l1:
                        gs_l1 = min(0.0, gs_l1)
                    if low_soc_active_l2:
                        gs_l2 = min(0.0, gs_l2)

                    gs_l1_rounded = round(gs_l1 / 10) * 10
                    gs_l1_rounded = max(-2400, min(2400, gs_l1_rounded))
                    
                    gs_l2_rounded = 0
                    if has_l2:
                        gs_l2_rounded = round(gs_l2 / 10) * 10
                        gs_l2_rounded = max(-2400, min(2400, gs_l2_rounded))

                    # L1 schreiben
                    device_payload_night_l1 = {}
                    if state.get("last_device_gs") != gs_l1_rounded:
                        device_payload_night_l1["GS"] = gs_l1_rounded
                        state["last_device_gs"] = gs_l1_rounded
                    
                    is_target_night_l1 = 10 if low_soc_active_l1 else 2400
                    if state.get("last_device_is") != is_target_night_l1:
                        device_payload_night_l1["IS"] = is_target_night_l1
                        state["last_device_is"] = is_target_night_l1
                        
                    if state.get("last_device_mm") != 0:
                        device_payload_night_l1["MM"] = 0
                        state["last_device_mm"] = 0
                        
                    if device_payload_night_l1:
                        sunenergy_write(sunenergy_ip, device_payload_night_l1)

                    if state.get("last_gs_written") is None or abs(state["last_gs_written"] - gs_l1_rounded) >= 10:
                        ha_set_number(gs_entity, gs_l1_rounded)
                        state["last_gs_written"] = gs_l1_rounded

                    # L2 schreiben (falls vorhanden)
                    if has_l2:
                        device_payload_night_l2 = {}
                        if state.get("last_device_gs_l2") != gs_l2_rounded:
                            device_payload_night_l2["GS"] = gs_l2_rounded
                            state["last_device_gs_l2"] = gs_l2_rounded
                        
                        is_target_night_l2 = 10 if low_soc_active_l2 else 2400
                        if state.get("last_device_is_l2") != is_target_night_l2:
                            device_payload_night_l2["IS"] = is_target_night_l2
                            state["last_device_is_l2"] = is_target_night_l2
                            
                        if state.get("last_device_mm_l2") != 0:
                            device_payload_night_l2["MM"] = 0
                            state["last_device_mm_l2"] = 0
                            
                        if device_payload_night_l2:
                            sunenergy_write(sunenergy_ip_l2, device_payload_night_l2)

                        if gs_entity_l2:
                            if state.get("last_gs_written_l2") is None or abs(state["last_gs_written_l2"] - gs_l2_rounded) >= 10:
                                ha_set_number(gs_entity_l2, gs_l2_rounded)
                                state["last_gs_written_l2"] = gs_l2_rounded

                    gs_new_rounded = gs_l1_rounded + gs_l2_rounded

                    log.info("Nacht: Aktive Regelung (MM=0) | L1_GS=%dW L2_GS=%dW | grid=%.0fW haus=%.0fW SOC_L1=%.0f%% SOC_L2=%.0f%%",
                             gs_l1_rounded, gs_l2_rounded, grid_p_raw, haus_p, curr_soc, curr_soc_l2)

                # CSV schreiben nachts
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
                    "is_target": is_target_night_l1 if not is_native else (10 if low_soc_active_l1 else 2400),
                    "hms_limit": 3600,
                    "hms_2000":  round(solar_p_2000, 1),
                    "hms_1600":  round(solar_p_1600, 1),
                    "hms_2000_lim": 2000,
                    "hms_1600_lim": 1600,
                    "soc_l2":    round(curr_soc_l2, 1) if has_l2 else 0.0,
                    "op_l2":     round(op_l2, 1) if has_l2 else 0.0,
                    "pv_l2":     round(pv_l2, 1) if has_l2 else 0.0,
                    "gs_l1":     round(gs_l1_rounded, 0),
                    "gs_l2":     round(gs_l2_rounded, 0),
                })

                # v1.8.5: Berechnete Werte als virtuelle HA-Sensoren pushen
                ha_push_sensor("sensor.sunenergy_hausverbrauch",  haus_p,      "W", "power",  "Hausverbrauch (Controller)")
                ha_push_sensor("sensor.sunenergy_grid_p",         grid_p_raw,  "W", "power",  "Netz aktuell (Controller)")
                ha_push_sensor("sensor.sunenergy_solar_p",        solar_p,     "W", "power",  "Solar gesamt (Controller)")
                ha_push_sensor("sensor.sunenergy_battery_ac",     battery_ac_est, "W", "power", "Batterie AC (Controller)")
                ha_push_sensor("sensor.sunenergy_battery_ac_l1",  battery_ac_est_l1, "W", "power", "Batterie L1 AC (Controller)")
                ha_push_sensor("sensor.sunenergy_battery_ac_l2",  battery_ac_est_l2, "W", "power", "Batterie L2 AC (Controller)")

                state["grid_p_filtered"] = grid_p_raw
                state["last_gs"]         = gs_new
                save_state_throttled(state)
                sleep_tick(TICK_S)
                continue

            # ------------------------------------------------------------------
            # 7. Tagregelung — universell für jeden SOC mit Spam-Schutz
            # ------------------------------------------------------------------
                set_active_mode(state, "bypass")
            elif feed_in_active:
                set_active_mode(state, "feed_in" if is_actively_feeding_in else "feed_in_standby")
            else:
                set_active_mode(state, "active")

            # Netz-Fehler bezüglich des Soll-Netzwertes (0W bzw. -500W bei manueller Einspeisung)
            grid_error = grid_p_raw - grid_target

            max_gs = 4800.0 if has_l2 else 2400.0

            if bypass_active:
                # Bypass-Modus: Nulleinspeisung ausgesetzt.
                # Wir berechnen gs_new über den PID-Regler, um Batterieladung zu maximieren.
                gs_last = safe_float(state, "last_gs", 0.0)
                _delta_day = calc_adaptive_gs_delta(grid_error)
                gs_new = gs_last + _delta_day
                
                # Zwangsladung/Hold-Time/Limits wie im normalen Modus anwenden
                hold_until = state.get("hold_until", 0.0)
                if time.monotonic() < hold_until:
                    gs_new = gs_last
                
                headroom_l1 = max(0.0, soc_max_limit - curr_soc)
                l2_charge_blocked = state.get("l2_charge_blocked", False)
                headroom_l2 = max(0.0, soc_max_limit - curr_soc_l2) if (has_l2 and not l2_charge_blocked) else 0.0
                total_headroom = headroom_l1 + headroom_l2
                if total_headroom <= 0.0:
                    gs_new = max(0.0, gs_new)
                
                gs_new = max(-max_gs, min(max_gs, gs_new))
                
                # Aufteilung unter Berücksichtigung von vollen Batterien (Durchreichen)
                if gs_new > 0:
                    # Entladen: Normale proportionale Aufteilung nach SOC
                    usable_soc_l1 = max(0.0, curr_soc - soc_min) if not low_soc_active_l1 else 0.0
                    usable_soc_l2 = max(0.0, curr_soc_l2 - soc_min) if (has_l2 and not low_soc_active_l2) else 0.0
                    total_usable = usable_soc_l1 + usable_soc_l2
                    if total_usable > 0:
                        ratio_l1 = usable_soc_l1 / total_usable
                        ratio_l2 = usable_soc_l2 / total_usable
                        gs_l1 = gs_new * ratio_l1
                        gs_l2 = gs_new * ratio_l2
                    else:
                        gs_l1 = 0.0
                        gs_l2 = 0.0
                else:
                    # Laden (gs_new <= 0): Begrenzung bei vollen Batterien (Durchreichen)
                    l1_full = curr_soc >= (soc_max_limit - 3.0)
                    l2_full = has_l2 and (curr_soc_l2 >= (soc_max_limit - 3.0))
                    
                    if l1_full and l2_full:
                        gs_l1 = pv_current
                        gs_l2 = pv_l2
                    elif l1_full:
                        gs_l1 = pv_current
                        gs_l2 = gs_new - gs_l1
                        if l2_charge_blocked:
                            gs_l2 = max(0.0, gs_l2)
                        gs_l2 = max(-2400.0, min(2400.0, gs_l2))
                    elif l2_full:
                        gs_l2 = pv_l2
                        gs_l1 = gs_new - gs_l2
                        gs_l1 = max(-2400.0, min(2400.0, gs_l1))
                    else:
                        # Beide nicht voll -> Proportional zum Headroom laden
                        if total_headroom > 0:
                            ratio_l1 = headroom_l1 / total_headroom
                            ratio_l2 = headroom_l2 / total_headroom
                            gs_l1 = gs_new * ratio_l1
                            gs_l2 = gs_new * ratio_l2
                        else:
                            gs_l1 = 0.0
                            gs_l2 = 0.0
            else:
                # GS Formel: gedämpft → gs_last + grid_error * 0.3, Rate-Limit ±120W/Tick
                gs_last = safe_float(state, "last_gs", 0.0)
                _delta_day = calc_adaptive_gs_delta(grid_error)
                gs_new = gs_last + _delta_day

                hold_until = state.get("hold_until", 0.0)
                if time.monotonic() < hold_until:
                    gs_new = gs_last

                # Anti-Windup bei vollen/nicht ladbaren Batterien (tagsüber)
                headroom_l1 = max(0.0, soc_max_limit - curr_soc)
                l2_charge_blocked = state.get("l2_charge_blocked", False)
                headroom_l2 = max(0.0, soc_max_limit - curr_soc_l2) if (has_l2 and not l2_charge_blocked) else 0.0
                total_headroom = headroom_l1 + headroom_l2
                if total_headroom <= 0.0:
                    gs_new = max(0.0, gs_new)

                if low_soc_active_l1 and (not has_l2 or low_soc_active_l2):
                    gs_new = min(0.0, gs_new)
                gs_new = max(-max_gs, min(max_gs, gs_new))

                # Aufteilung auf L1 und L2
                gs_l1 = 0.0
                gs_l2 = 0.0
                if gs_new > 0:
                    # Entladen proportional zum SOC
                    usable_soc_l1 = max(0.0, curr_soc - soc_min) if not low_soc_active_l1 else 0.0
                    usable_soc_l2 = max(0.0, curr_soc_l2 - soc_min) if (has_l2 and not low_soc_active_l2) else 0.0
                    total_usable = usable_soc_l1 + usable_soc_l2
                    if total_usable > 0:
                        ratio_l1 = usable_soc_l1 / total_usable
                        ratio_l2 = usable_soc_l2 / total_usable
                        gs_l1 = gs_new * ratio_l1
                        gs_l2 = gs_new * ratio_l2
                        if gs_l1 > 2400:
                            rem = gs_l1 - 2400
                            gs_l1 = 2400
                            if usable_soc_l2 > 0.0:
                                gs_l2 = min(2400, gs_l2 + rem)
                        elif gs_l2 > 2400:
                            rem = gs_l2 - 2400
                            gs_l2 = 2400
                            if usable_soc_l1 > 0.0:
                                gs_l1 = min(2400, gs_l1 + rem)
                elif gs_new < 0:
                    # Laden proportional zum Headroom
                    if total_headroom > 0:
                        ratio_l1 = headroom_l1 / total_headroom
                        ratio_l2 = headroom_l2 / total_headroom
                        gs_l1 = gs_new * ratio_l1
                        gs_l2 = gs_new * ratio_l2
                        if gs_l1 < -2400:
                            rem = gs_l1 + 2400
                            gs_l1 = -2400
                            if headroom_l2 > 0.0:
                                gs_l2 = max(-2400, gs_l2 + rem)
                        elif gs_l2 < -2400:
                            rem = gs_l2 + 2400
                            gs_l2 = -2400
                            if headroom_l1 > 0.0:
                                gs_l1 = max(-2400, gs_l1 + rem)

            # Kreuzladung Hold-Time aktiv? Dann Laden (negatives GS) verhindern
            if time.time() < state.get("kreuzladung_hold_until", 0):
                gs_l1 = max(0.0, gs_l1)
                gs_l2 = max(0.0, gs_l2)
                log.debug("Kreuzladung Hold-Time aktiv — Laden (negatives GS) gesperrt")

            # Sicherheitsgrenzen bei niedrigem SOC anwenden
            if low_soc_active_l1:
                gs_l1 = min(0.0, gs_l1)
            if low_soc_active_l2:
                gs_l2 = min(0.0, gs_l2)

            # Vorläufiges Runden für Schutzlogiken (HMS- und IS-Drosselung)
            gs_l1_rounded = round(gs_l1 / 10) * 10
            gs_l1_rounded = max(-2400, min(2400, gs_l1_rounded))
            
            gs_l2_rounded = 0
            if has_l2:
                gs_l2_rounded = round(gs_l2 / 10) * 10
                gs_l2_rounded = max(-2400, min(2400, gs_l2_rounded))

            gs_new_rounded = gs_l1_rounded + gs_l2_rounded

            # HMS stufenlos regeln
            hms_limit_last = safe_float(state, "last_hms_limit", 3600.0)
            hms_change = 0.0

            # Bei aktiver manueller Einspeisung oder Bypass Hoymiles voll öffnen
            if bypass_active:
                hms_limit_new = 3600.0
            elif is_actively_feeding_in:
                hms_limit_new = 3600.0
            elif (curr_soc < (soc_max_limit - 3.0) or (has_l2 and not l2_charge_blocked and curr_soc_l2 < (soc_max_limit - 3.0))) and gs_new_rounded > -2350:
                # Akku nicht voll und lädt nicht am Limit (IS): Hoymiles voll öffnen,
                # damit jegliche Solarleistung zum Laden des Akkus genutzt werden kann.
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
            elif grid_error > 50 or (battery_ac_est > 20.0 and hms_limit_last < 3600.0):
                # Bezug oder Batterie-Entladung bei gedrosselten Hoymiles:
                # Hoymiles freigeben (mehr erzeugen lassen), um Batterie-Entladung zu minimieren.
                effective_deficit = grid_error + max(0.0, battery_ac_est)
                hms_change = effective_deficit * 0.5
                hms_change = max(-400.0, min(800.0, hms_change))
                hms_limit_new = hms_limit_last + hms_change
            elif curr_soc < soc_max_limit or (has_l2 and not l2_charge_blocked and curr_soc_l2 < soc_max_limit):
                # Akku nicht voll und keine Abweichung vom Sollwert: stufenlos regeln
                # um Überschwingen/Oszillationen nahe der Vollladung zu verhindern.
                if solar_p >= hms_limit_last - 100:
                    hms_change = 80.0
                hms_change = max(-400.0, min(400.0, hms_change))
                hms_limit_new = hms_limit_last + hms_change
            else:
                hms_limit_new = hms_limit_last

            hms_limit_new = max(0.0, min(3600.0, hms_limit_new))
            # Fix 2 — HMS-Anpassung bei aktivem Transfer:
            if p_transfer > 10.0:
                hms_limit_new = min(3600.0, haus_p + p_transfer)

            # v2.3.6: Ladekapazität ab 1% unter dem Limit auf 0 setzen, da das BMS dort bereits abriegelt
            charge_capacity_l1 = 2400.0 if curr_soc < (soc_max_limit - 1.0) else 0.0
            charge_capacity_l2 = 2400.0 if (has_l2 and not l2_charge_blocked and curr_soc_l2 < (soc_max_limit - 1.0)) else 0.0
            hms_limit_new = max(hms_limit_new, haus_p + charge_capacity_l1 + charge_capacity_l2)

            hms_limit_new = max(0.0, min(3600.0, hms_limit_new))
            state["last_hms_limit"] = hms_limit_new

            # HMS Limits berechnen
            limit_2000, limit_1600 = calc_hms_limits(
                hms_limit_new, solar_p_2000, solar_p_1600,
                hms_2000_online, hms_1600_online
            )

            # Drossel-Flag für HA/Visualisierung und Batterie-Entkoppelung setzen
            # Wir drosseln das Carport (IS) auch direkt, wenn die Akkus fast voll sind und Einspeisung vorliegt
            akkus_voll = total_headroom <= 0.0
            drosseln = ((hms_limit_new < 3500.0) and (solar_p >= hms_limit_new - 150.0) and (grid_error <= 50.0)) or (akkus_voll and grid_p_raw < -50.0)
            state["drosseln"] = drosseln

            # IS Limit der Batterie anpassen
            # L1
            is_native = use_native_pid and not state.get("in_fallback_mode", False)
            if low_soc_active_l1:
                is_target_l1 = 10
            elif bypass_active or is_actively_feeding_in:
                is_target_l1 = 2400
            elif akkus_voll and drosseln:
                # v2.3.8: Bei vollen Akkus den Anstiegs-Limiter umgehen und IS direkt stabilisieren
                is_stable = max(10, int(haus_p - solar_p))
                is_target_l1 = is_stable
                state["last_is"] = is_stable
            elif is_native and pv_current > 50.0:
                # v2.1.5: Permanente native PV-Drosselung (vorausschauende Begrenzung auf Restbedarf)
                is_target_l1 = max(10, haus_p - solar_p)
            elif curr_soc >= (soc_max_limit - 3.0) or (not is_native and (gs_l1_rounded < -200) and (-50.0 <= pb_current < 150.0)):
                if drosseln or (not is_native and (gs_l1_rounded < -200) and (-50.0 <= pb_current < 150.0)):
                    restbedarf = max(0, int(haus_p - solar_p))
                    # v2.1.9: L2-Ladefähigkeit einbeziehen, um L1s AC-Ausgabe für L2-Ladung freizugeben (Deadlock-Schutz)
                    l2_headroom = 0.0
                    if has_l2 and curr_soc_l2 < soc_max_limit:
                        fade_out = max(0.0, min(1.0, (soc_max_limit - curr_soc_l2) / 5.0))
                        l2_headroom = 2400.0 * fade_out

                    target_val = min(pv_current, restbedarf + l2_headroom)
                    # Mindestlimit is_floor verhindert IS-Sägezahn (Drosselung max. bis max(10, restbedarf))
                    is_floor = max(10, restbedarf)
                    target_val = max(is_floor, target_val)
                    
                    # v2.2.10: Sanfter Abfall bei Drosselung (max -250W/Tick), außer bei starker Einspeisung (< -400W)
                    if grid_p_raw < -400.0:
                        is_target_l1 = target_val
                    else:
                        is_target_l1 = max(target_val, safe_float(state, "last_device_is", 2400.0) - 250)
                else:
                    # v2.2.10: Sofortige Freigabe bei echtem Netzbezug (>400W), sonst sanfter Anstieg (+100W/Tick)
                    if grid_p_raw > 400.0:
                        is_target_l1 = 2400
                    else:
                        is_target_l1 = min(2400, safe_float(state, "last_device_is", 2400.0) + 100)
            else:
                is_target_l1 = 2400

            # L2
            if not has_l2:
                is_target_l2 = 2400
            elif low_soc_active_l2:
                is_target_l2 = 10
            elif bypass_active or is_actively_feeding_in:
                is_target_l2 = 2400
            elif pv_l2 <= 10.0:
                # L2 hat keine PV-Module -> Keine Drosselung nötig, bleibt auf Maximum.
                # Verhindert unnötige Schreibzugriffe über WLAN an L2.
                is_target_l2 = 2400
            elif akkus_voll and drosseln:
                # v2.3.8: Bei vollen Akkus den Anstiegs-Limiter umgehen und IS direkt stabilisieren
                is_stable = max(10, int(haus_p - solar_p))
                is_target_l2 = is_stable
                state["last_is_l2"] = is_stable
            elif is_native and pv_l2 > 50.0:
                # v2.1.5: Permanente native PV-Drosselung (vorausschauende Begrenzung auf Restbedarf)
                is_target_l2 = max(10, haus_p - solar_p)
            elif curr_soc_l2 >= (soc_max_limit - 3.0) or (not is_native and (gs_l2_rounded < -200) and (-50.0 <= pb_l2 < 150.0)):
                if drosseln or (not is_native and (gs_l2_rounded < -200) and (-50.0 <= pb_l2 < 150.0)):
                    restbedarf = max(0, int(haus_p - solar_p))
                    # v2.1.9: L1-Ladefähigkeit einbeziehen, um L2s AC-Ausgabe für L1-Ladung freizugeben (symmetrischer Deadlock-Schutz)
                    l1_headroom = 0.0
                    if curr_soc < soc_max_limit:
                        fade_out = max(0.0, min(1.0, (soc_max_limit - curr_soc) / 5.0))
                        l1_headroom = 2400.0 * fade_out

                    target_val = min(pv_l2, restbedarf + l1_headroom)
                    # Mindestlimit is_floor verhindert IS-Sägezahn
                    is_floor = max(10, restbedarf)
                    target_val = max(is_floor, target_val)
                    
                    # v2.2.10: Sanfter Abfall bei Drosselung (max -250W/Tick), außer bei starker Einspeisung (< -400W)
                    if grid_p_raw < -400.0:
                        is_target_l2 = target_val
                    else:
                        is_target_l2 = max(target_val, safe_float(state, "last_device_is_l2", 2400.0) - 250)
                else:
                    # v2.2.10: Sofortige Freigabe bei echtem Netzbezug (>400W), sonst sanfter Anstieg (+100W/Tick)
                    if grid_p_raw > 400.0:
                        is_target_l2 = 2400
                    else:
                        is_target_l2 = min(2400, safe_float(state, "last_device_is_l2", 2400.0) + 100)
            else:
                is_target_l2 = 2400

            # Fix 1 — IS-Anpassung bei aktivem Transfer:
            if p_transfer > 10.0:
                restbedarf = max(0, int(haus_p - solar_p))
                if curr_soc > curr_soc_l2:
                    # L1 ist Quelle -> IS L1 anheben
                    is_floor = max(10, restbedarf + int(p_transfer))
                    is_target_l1 = max(is_floor, is_target_l1)
                else:
                    # L2 ist Quelle -> IS L2 anheben
                    is_floor = max(10, restbedarf + int(p_transfer))
                    is_target_l2 = max(is_floor, is_target_l2)

            # Runden und Grenzen L1
            is_target_l1 = max(10, min(2400, round(is_target_l1 / 10) * 10))
            state["last_is"] = is_target_l1
            is_target = is_target_l1 # für Rückwärtskompatibilität

            # Runden und Grenzen L2
            is_target_l2 = max(10, min(2400, round(is_target_l2 / 10) * 10))
            state["last_is_l2"] = is_target_l2

            # ==================================================================
            # v2.1.8: SOC-Angleichung für L1/L2 im manuellen Modus via AC-AC-Transfer
            # ==================================================================
            p_transfer = 0.0
            if not is_native and has_l2:
                soc_max_curr = max(curr_soc, curr_soc_l2)
                soc_diff = curr_soc - curr_soc_l2
                
                if soc_max_curr > 80.0 and abs(soc_diff) > 5.0:
                    if soc_diff > 0.0:
                        # L1 is fuller -> Transfer L1 -> L2
                        src_is_l1 = True
                        soc_src, soc_dest = curr_soc, curr_soc_l2
                        pv_src, gs_src_rounded = pv_current, gs_l1_rounded
                        is_target_src, gs_src = is_target_l1, gs_l1
                        gs_dest = gs_l2
                    else:
                        # L2 is fuller -> Transfer L2 -> L1
                        src_is_l1 = False
                        soc_src, soc_dest = curr_soc_l2, curr_soc
                        pv_src, gs_src_rounded = pv_l2, gs_l2_rounded
                        is_target_src, gs_src = is_target_l2, gs_l2
                        gs_dest = gs_l1
                    
                    if pv_src > gs_src_rounded and soc_dest < soc_max_limit and soc_src > soc_min:
                        # Berechne Roh-Transferleistung
                        if soc_src >= (soc_max_limit - 3.0):
                            # Transfer-Boost bei vollem Quellspeicher
                            p_transfer_raw = pv_src - gs_src_rounded
                        else:
                            # Quelle lädt noch -> Proportionale Regelung
                            k_p = 15.0
                            p_transfer_raw = (abs(soc_diff) - 5.0) * k_p
                        
                        # stufenloses Abregeln (Fade-Out), wenn dest sich 95% nähert
                        fade_out = max(0.0, min(1.0, (soc_max_limit - soc_dest) / 5.0))
                        p_transfer_raw *= fade_out
                        
                        # Gedeckelt auf den lokalen solaren Überschuss der Quelle
                        solar_excess = pv_src - gs_src_rounded
                        
                        # Begrenzung auf die freien AC-Kapazitäten beider Geräte
                        max_possible_src_increase = max(0.0, is_target_src - gs_src)
                        max_possible_dest_charge = max(0.0, 2400.0 + gs_dest)
                        
                        p_transfer_target = min(p_transfer_raw, solar_excess, max_possible_src_increase, max_possible_dest_charge)
                        p_transfer_target = max(0.0, p_transfer_target)
                        
                        # v2.5.1: Transfer-Sperre wenn Quellspeicher kein eigenes PV hat (AC-AC Kreuzladungs-Vermeidung)
                        src_has_pv = (pv_current >= 10.0) if src_is_l1 else (pv_l2 >= 10.0)
                        if not src_has_pv:
                            p_transfer_target = 0.0
                        
                        # v2.5.5: Transfer-Sperre wenn der Zielspeicher (L2) AC-ladeblockiert ist
                        if src_is_l1 and state.get("l2_charge_blocked", False):
                            p_transfer_target = 0.0
                        
                        # Slew-Rate Limit beim Hochfahren, sofortiges Runterfahren bei Wolken
                        last_p_transfer = state.get("last_p_transfer", 0.0)
                        if p_transfer_target > last_p_transfer:
                            p_transfer = min(p_transfer_target, last_p_transfer + 50.0)
                        else:
                            p_transfer = p_transfer_target
                        
                        state["last_p_transfer"] = p_transfer
                        
                        if p_transfer > 10.0:
                            if src_is_l1:
                                gs_l1 += p_transfer
                                gs_l2 -= p_transfer
                            else:
                                gs_l2 += p_transfer
                                gs_l1 -= p_transfer
                            log.info("SOC-Angleichung aktiv: Transferiere %.1fW von %s zu %s (SOC L1: %.1f%%, L2: %.1f%%, solarer Überschuss L1: %.1fW, L2: %.1fW, IS_L1: %dW, IS_L2: %dW)",
                                     p_transfer, 
                                     "L1" if src_is_l1 else "L2", 
                                     "L2" if src_is_l1 else "L1",
                                     curr_soc, curr_soc_l2, pv_current, pv_l2, is_target_l1, is_target_l2)
                    else:
                        state["last_p_transfer"] = 0.0
                else:
                    state["last_p_transfer"] = 0.0
            else:
                if "last_p_transfer" in state:
                    state["last_p_transfer"] = 0.0

            # Finales Runden der GS-Sollwerte nach Transfer
            gs_l1_rounded = round(gs_l1 / 10) * 10
            gs_l1_rounded = max(-2400, min(2400, gs_l1_rounded))

            gs_l2_rounded = 0
            if has_l2:
                gs_l2_rounded = round(gs_l2 / 10) * 10
                gs_l2_rounded = max(-2400, min(2400, gs_l2_rounded))

            gs_new_rounded = gs_l1_rounded + gs_l2_rounded

            # HA-Schreiben durchführen
            if not is_native:
                # MM AUS — wir regeln (nur schalten, wenn nicht bereits aus)
                current_mm_state = ha_get_state(mm_switch, "on")
                if current_mm_state != "off":
                    ha_switch(mm_switch, False)
                if has_l2 and mm_switch_l2:
                    current_mm_state_l2 = ha_get_state(mm_switch_l2, "on")
                    if current_mm_state_l2 != "off":
                        ha_switch(mm_switch_l2, False)

                # GS Sollwert in HA schreiben (nur bei nennenswerten Änderungen)
                if state.get("last_gs_written") is None or abs(state["last_gs_written"] - gs_l1_rounded) >= 10:
                    ha_set_number(gs_entity, gs_l1_rounded)
                    state["last_gs_written"] = gs_l1_rounded
                
                if has_l2 and gs_entity_l2:
                    if state.get("last_gs_written_l2") is None or abs(state["last_gs_written_l2"] - gs_l2_rounded) >= 10:
                        ha_set_number(gs_entity_l2, gs_l2_rounded)
                        state["last_gs_written_l2"] = gs_l2_rounded
            else:
                # Im nativen Modus schreiben wir GS=0 in HA
                if state.get("last_gs_written") != 0:
                    ha_set_number(gs_entity, 0)
                    state["last_gs_written"] = 0
                if has_l2 and gs_entity_l2 and state.get("last_gs_written_l2") != 0:
                    ha_set_number(gs_entity_l2, 0)
                    state["last_gs_written_l2"] = 0

            # Direkt ans Gerät schreiben (nur bei Änderungen)
            # L1
            reported_is = se_data.get("IS") if se_data else None
            reported_gs = se_data.get("GS") if se_data else None
            reported_is_f = float(reported_is) if reported_is is not None else None
            reported_gs_f = float(reported_gs) if reported_gs is not None else None

            mismatch_is_l1_log = state.get("last_device_is") == is_target_l1 and reported_is_f is not None and abs(reported_is_f - is_target_l1) >= 10
            if mismatch_is_l1_log:
                log.warning("⚠️ L1 IS mismatch: reported=%.0fW, target=%dW. Enforcing...", reported_is_f, is_target_l1)

            device_payload_l1 = {}
            if (state.get("last_device_is") != is_target_l1) or (reported_is_f is not None and abs(reported_is_f - is_target_l1) >= 10):
                device_payload_l1["IS"] = is_target_l1
                state["last_device_is"] = is_target_l1
            
            if not is_native:
                mismatch_gs_l1_log = state.get("last_device_gs") == gs_l1_rounded and reported_gs_f is not None and abs(reported_gs_f - gs_l1_rounded) >= 10
                if mismatch_gs_l1_log:
                    log.warning("⚠️ L1 GS mismatch: reported=%.0fW, target=%dW. Enforcing...", reported_gs_f, gs_l1_rounded)

                if state.get("last_device_mm") != 0:
                    device_payload_l1["MM"] = 0
                    state["last_device_mm"] = 0
                if (state.get("last_device_gs") != gs_l1_rounded) or (reported_gs_f is not None and abs(reported_gs_f - gs_l1_rounded) >= 10):
                    device_payload_l1["GS"] = gs_l1_rounded
                    state["last_device_gs"] = gs_l1_rounded
                
            if device_payload_l1:
                sunenergy_write(sunenergy_ip, device_payload_l1)

            # L2
            if has_l2:
                reported_is_l2 = se_data_l2.get("IS") if se_data_l2 else None
                reported_gs_l2 = se_data_l2.get("GS") if se_data_l2 else None
                reported_is_l2_f = float(reported_is_l2) if reported_is_l2 is not None else None
                reported_gs_l2_f = float(reported_gs_l2) if reported_gs_l2 is not None else None

                mismatch_is_l2_log = state.get("last_device_is_l2") == is_target_l2 and reported_is_l2_f is not None and abs(reported_is_l2_f - is_target_l2) >= 10
                if mismatch_is_l2_log:
                    log.warning("⚠️ L2 IS mismatch: reported=%.0fW, target=%dW. Enforcing...", reported_is_l2_f, is_target_l2)

                device_payload_l2 = {}
                if (state.get("last_device_is_l2") != is_target_l2) or (reported_is_l2_f is not None and abs(reported_is_l2_f - is_target_l2) >= 10):
                    device_payload_l2["IS"] = is_target_l2
                    state["last_device_is_l2"] = is_target_l2
                
                if not is_native:
                    mismatch_gs_l2_log = state.get("last_device_gs_l2") == gs_l2_rounded and reported_gs_l2_f is not None and abs(reported_gs_l2_f - gs_l2_rounded) >= 10
                    if mismatch_gs_l2_log:
                        log.warning("⚠️ L2 GS mismatch: reported=%.0fW, target=%dW. Enforcing...", reported_gs_l2_f, gs_l2_rounded)

                    if state.get("last_device_mm_l2") != 0:
                        device_payload_l2["MM"] = 0
                        state["last_device_mm_l2"] = 0
                    if (state.get("last_device_gs_l2") != gs_l2_rounded) or (reported_gs_l2_f is not None and abs(reported_gs_l2_f - gs_l2_rounded) >= 10):
                        device_payload_l2["GS"] = gs_l2_rounded
                        state["last_device_gs_l2"] = gs_l2_rounded
                        
                if device_payload_l2:
                    sunenergy_write(sunenergy_ip_l2, device_payload_l2)

            # Hoymiles Limits setzen (mit Signalverlust-Schutz)
            # is_tick wird für Trägheitsprüfung verwendet
            is_tick = state.get("is_tick", 0) + 1
            state["is_tick"] = is_tick
            do_is_update = (is_tick % 6 == 0)

            if hms_2000_online:
                last_written_2000 = safe_float(state, "last_hms_2000_lim", 2000.0)
                # Senden wenn der neue Wert um >= 50W vom zuletzt geschriebenen abweicht
                # ODER wenn Inverter trotz Drosselung > 50W über Limit liegt
                need_send_2000 = (abs(last_written_2000 - limit_2000) >= 50) or (drosseln and solar_p_2000 > limit_2000 + 50 and do_is_update)
                if need_send_2000:
                    ha_set_number(hms_2000_entity, limit_2000)
                    state["last_hms_2000_lim"] = limit_2000

            if hms_1600_online:
                last_written_1600 = safe_float(state, "last_hms_1600_lim", 1600.0)
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

            # CSV schreiben am Tag
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
                "soc_l2":    round(curr_soc_l2, 1) if has_l2 else 0.0,
                "op_l2":     round(op_l2, 1) if has_l2 else 0.0,
                "pv_l2":     round(pv_l2, 1) if has_l2 else 0.0,
                "gs_l1":     round(gs_l1_rounded, 0),
                "gs_l2":     round(gs_l2_rounded, 0),
            })

            # v1.8.5: Berechnete Werte als virtuelle HA-Sensoren pushen
            ha_push_sensor("sensor.sunenergy_hausverbrauch",  haus_p,      "W", "power",  "Hausverbrauch (Controller)")
            ha_push_sensor("sensor.sunenergy_grid_p",         grid_p_raw,  "W", "power",  "Netz aktuell (Controller)")
            ha_push_sensor("sensor.sunenergy_solar_p",        solar_p,     "W", "power",  "Solar gesamt (Controller)")
            ha_push_sensor("sensor.sunenergy_battery_ac",     battery_ac_est, "W", "power", "Batterie AC (Controller)")
            ha_push_sensor("sensor.sunenergy_battery_ac_l1",  battery_ac_est_l1, "W", "power", "Batterie L1 AC (Controller)")
            ha_push_sensor("sensor.sunenergy_battery_ac_l2",  battery_ac_est_l2, "W", "power", "Batterie L2 AC (Controller)")

            # last_hms_2000/1600_lim werden jetzt nur noch bei echten Schreibbefehlen aktualisiert (drift-safe)

            state["grid_p_filtered"] = grid_p_raw
            state["solar_p_last"]    = solar_p
            state["haus_p_last"]     = haus_p
            state["last_gs"]         = gs_new
            state["solar_p_2000_last"] = solar_p_2000
            state["solar_p_1600_last"] = solar_p_1600
            save_state_throttled(state)

        except Exception as e:
            log.error("Fehler im Regelzyklus: %s", e, exc_info=True)

        elapsed = time.monotonic() - tick_start
        sleep_tick(TICK_S - elapsed)

    # ------------------------------------------------------------------
    # v1.9.2: Sauberer Shutdown — Übergabe an Geräte-Selbstregelung.
    # MM=1: das Gerät regelt die Nulleinspeisung selbst weiter, statt mit
    # einem eingefrorenen GS-Sollwert stehen zu bleiben.
    # ------------------------------------------------------------------
    log.info("Shutdown — übergebe an Geräte-Selbstregelung (MM=1, GS=0)...")
    try:
        ha_switch(mm_switch, True)
        ha_set_number(gs_entity, 0)
        sunenergy_write(sunenergy_ip, {"MM": 1, "GS": 0})
        state["last_device_gs"] = None
        state["last_device_mm"] = None
        state["last_device_is"] = None
        state["last_gs_written"] = None
        
        if has_l2:
            if mm_switch_l2:
                ha_switch(mm_switch_l2, True)
            if gs_entity_l2:
                ha_set_number(gs_entity_l2, 0)
            sunenergy_write(sunenergy_ip_l2, {"MM": 1, "GS": 0})
            state["last_device_gs_l2"] = None
            state["last_device_mm_l2"] = None
            state["last_device_is_l2"] = None
            state["last_gs_written_l2"] = None
            
        save_state(state)
    except Exception as e:
        log.error("Fehler beim Shutdown-Safe-State: %s", e)
    log.info("Controller beendet.")


if __name__ == "__main__":
    main()

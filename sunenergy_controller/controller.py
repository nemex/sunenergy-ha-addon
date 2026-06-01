#!/usr/bin/env python3
"""
SunEnergy XT Controller v2.0
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
    "gs", "op", "is_target", "hms_limit", "hms_2000", "hms_1600"
]

def csv_log(row: dict):
    try:
        write_header = not os.path.exists(CSV_PATH)
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
    grid_p: float,
    solar_p_2000: float,
    solar_p_1600: float,
    haus_p: float,
    hms_1600_online: bool,
    tag_modus: bool,
    drosseln: bool,
) -> tuple[float, float]:
    """Berechnet HMS Limits. drosseln=True wenn zu viel produziert wird."""
    max_2000 = 2000.0
    max_1600 = 1600.0

    if not tag_modus or not drosseln:
        return max_2000, max_1600

    total = solar_p_2000 + solar_p_1600
    if total > 50:
        ratio_2000 = solar_p_2000 / total
        ratio_1600 = solar_p_1600 / total if hms_1600_online else 0
    else:
        ratio_2000 = 0.6
        ratio_1600 = 0.4 if hms_1600_online else 0

    # Zielleistung: genau Hausverbrauch
    hms_target = max(100.0, haus_p)

    limit_2000 = min(int(hms_target * ratio_2000), max_2000)
    limit_1600 = min(int(hms_target * ratio_1600), max_1600) if hms_1600_online else 0

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
    soc_normal_max  = float(opts["soc_normal_max"])    # 93%
    soc_min         = float(opts["soc_min"])            # 10%
    calib_days      = float(opts["calibration_days"])  # 15
    sunenergy_ip    = opts.get("sunenergy_ip", "192.168.178.94")

    # SA auf Normalwert setzen beim Start
    ha_set_number(sa_entity, soc_normal_max)

    # State zurücksetzen
    state["active_mode"] = "night"
    state["last_calibration_ts"] = time.time()
    save_state(state)
    log.info("State zurückgesetzt, SA=%s%%", soc_normal_max)

    while True:
        try:
            tick_start = time.monotonic()

            # ------------------------------------------------------------------
            # 1. Messwerte lesen
            # ------------------------------------------------------------------
            grid_p_raw = float(ha_get_state(grid_sensor, "0") or 0)
            curr_soc   = float(ha_get_state(soc_sensor, "0") or 0)
            haus_p     = abs(float(ha_get_state("sensor.hausverbrauch_aktuell", "0") or 0))

            solar_p_2000 = abs(float(ha_get_state("sensor.hoymiles_hms_2000_4t_power", "0") or 0))
            solar_p_1600 = abs(float(ha_get_state("sensor.hoymiles_hms_1600_4t_power", "0") or 0))
            hms_1600_online = ha_get_state("binary_sensor.hoymiles_hms_1600_4t_reachable", "off") == "on"
            solar_p = solar_p_2000 + solar_p_1600

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
            op_current = float(se_data.get("OP", 0))
            state["soc"] = curr_soc

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
                time.sleep(TICK_S)
                continue

            if state["active_mode"] == "calibration" and curr_soc >= 100:
                log.info("Zwangsladung abgeschlossen!")
                state["last_calibration_ts"] = time.time()
                state["active_mode"] = "night"
                ha_set_number(sa_entity, soc_normal_max)
                ha_switch(mm_switch, True)
                ha_set_number(gs_entity, 0)
                sunenergy_write(sunenergy_ip, {"IS": 2400})
                save_state(state)
                time.sleep(TICK_S)
                continue

            # ------------------------------------------------------------------
            # 6. Nachtmodus — GS weiter aktiv regeln für Akkuentladung
            # ------------------------------------------------------------------
            if not sun_above:
                if state["active_mode"] != "night":
                    log.info("Nachtmodus: IS=2400, HMS voll")
                    sunenergy_write(sunenergy_ip, {"IS": 2400})
                    ha_set_number(hms_2000_entity, 2000)
                    if hms_1600_online:
                        ha_set_number(hms_1600_entity, 1600)

                state["active_mode"] = "night"

                # GS weiter regeln: Akku entlädt bei Netzbezug, lädt bei Überschuss
                # Dämpfung: nur 50% des Fehlers korrigieren → verhindert Oszillation
                gs_last = float(state.get("last_gs", 0))
                gs_new = gs_last + grid_p_raw * 0.5
                gs_new = max(-2400, min(2400, gs_new))

                ha_switch(mm_switch, False)
                ha_set_number(gs_entity, gs_new)
                sunenergy_write(sunenergy_ip, {"MM": 0, "GS": int(gs_new)})

                log.info("Nacht: GS=%dW | grid=%.0fW haus=%.0fW SOC=%.0f%%",
                         gs_new, grid_p_raw, haus_p, curr_soc)

                csv_log({
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "mode": "night",
                    "soc": round(curr_soc, 1),
                    "grid_p": round(grid_p_raw, 1),
                    "haus_p": round(haus_p, 1),
                    "solar_p": 0,
                    "gs": round(gs_new, 0),
                    "op": round(op_current, 1),
                    "is_target": 2400,
                    "hms_limit": 3600,
                    "hms_2000": 0,
                    "hms_1600": 0,
                })

                state["grid_p_filtered"] = grid_p_raw
                state["last_gs"] = gs_new
                save_state(state)
                time.sleep(TICK_S)
                continue

            # ------------------------------------------------------------------
            # 7. Tagregelung — universell für jeden SOC
            # ------------------------------------------------------------------
            state["active_mode"] = "active"

            # GS Formel: gedämpft → gs_last + grid_p * 0.5
            # Verhindert Oszillation, pendelt sich bei ±25W ein
            gs_last = float(state.get("last_gs", 0))
            gs_new = gs_last + grid_p_raw * 0.5
            gs_new = max(-2400, min(2400, gs_new))

            # MM AUS — wir regeln
            ha_switch(mm_switch, False)
            ha_set_number(gs_entity, gs_new)

            # IS: begrenzt DC-Carport
            # Wenn Einspeisung (grid < -25W) → IS reduzieren
            # Wenn Bezug (grid > 25W) → IS erhöhen
            # Einfache Formel: IS = haus - solar (was HMS nicht liefert)
            if grid_p_raw < -75:
                # Deutlicher Überschuss → IS runter (größerer Deadband verhindert Oszillation)
                is_target = max(0, int(haus_p - solar_p))
                drosseln = True
            elif grid_p_raw > 75:
                # Deutlicher Bezug → IS hoch
                is_target = min(2400, int(haus_p - solar_p + grid_p_raw))
                drosseln = False
            else:
                # Im Deadband → IS halten
                is_target = max(0, int(haus_p - solar_p))
                drosseln = False

            is_target = max(0, min(2400, is_target))

            # HMS Limits
            limit_2000, limit_1600 = calc_hms_limits(
                grid_p_raw, solar_p_2000, solar_p_1600,
                haus_p, hms_1600_online, True, drosseln
            )

            # Schreiben
            sunenergy_write(sunenergy_ip, {"IS": is_target, "MM": 0})

            curr_2000 = float(ha_get_state(hms_2000_entity, "2000") or 2000)
            if abs(curr_2000 - limit_2000) >= 50:
                ha_set_number(hms_2000_entity, limit_2000)

            if hms_1600_online:
                curr_1600 = float(ha_get_state(hms_1600_entity, "1600") or 1600)
                if abs(curr_1600 - limit_1600) >= 50:
                    ha_set_number(hms_1600_entity, limit_1600)

            log.info("GS=%dW IS=%dW HMS=%d/%dW | grid=%.0fW haus=%.0fW solar=%.0fW SOC=%.0f%%",
                     gs_new, is_target, limit_2000, limit_1600,
                     grid_p_raw, haus_p, solar_p, curr_soc)

            # Vollladung erkennen
            if curr_soc >= 100:
                state["last_calibration_ts"] = time.time()

            # CSV
            csv_log({
                "ts":       time.strftime("%Y-%m-%d %H:%M:%S"),
                "mode":     state["active_mode"],
                "soc":      round(curr_soc, 1),
                "grid_p":   round(grid_p_raw, 1),
                "haus_p":   round(haus_p, 1),
                "solar_p":  round(solar_p, 1),
                "gs":       round(gs_new, 0),
                "op":       round(op_current, 1),
                "is_target": is_target,
                "hms_limit": round(limit_2000 + limit_1600, 0),
                "hms_2000":  round(solar_p_2000, 1),
                "hms_1600":  round(solar_p_1600, 1),
            })

            state["grid_p_filtered"] = grid_p_raw
            state["solar_p_last"]    = solar_p
            state["haus_p_last"]     = haus_p
            state["last_gs"]         = gs_new
            save_state(state)

        except Exception as e:
            log.error("Fehler im Regelzyklus: %s", e, exc_info=True)

        elapsed = time.monotonic() - tick_start
        time.sleep(max(0, TICK_S - elapsed))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
SunEnergy XT Controller
=======================
Zero-feed-in PI-controller for SunEnergyXT 500 Pro
with Hoymiles HMS throttling via OpenDTU.

Konzept:
- Lokaler Nulleinspeisemodus (MM) AN  = Gerät regelt selbst (Nacht, kein Überschuss)
- Lokaler Nulleinspeisemodus (MM) AUS = Wir regeln über GS-Sollwert (Überschuss vorhanden)
- HMS-Drosselung ab SOC >= hms_throttle_soc %
- SA (Systemladegrenze) = soc_normal_max % im Normalbetrieb
- Zwangsladung alle calibration_days Tage bei Sonnenuntergang
"""

import json
import logging
import os
import time
import math
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
# Konfiguration aus Add-on Options laden
# ---------------------------------------------------------------------------
OPTIONS_PATH = "/data/options.json"

def load_options() -> dict:
    with open(OPTIONS_PATH) as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# Home Assistant API
# ---------------------------------------------------------------------------
HA_URL = "http://supervisor/core"
HA_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

def ha_get(entity_id: str):
    """Liest einen HA-Sensor-Wert."""
    try:
        r = requests.get(
            f"{HA_URL}/api/states/{entity_id}",
            headers={"Authorization": f"Bearer {HA_TOKEN}"},
            timeout=5,
        )
        if r.status_code == 200:
            return r.json()
        log.warning("HA GET %s → %s", entity_id, r.status_code)
    except Exception as e:
        log.error("HA GET %s Fehler: %s", entity_id, e)
    return None

def ha_get_state(entity_id: str, default=None):
    """Gibt den State-Wert zurück."""
    data = ha_get(entity_id)
    if data and data.get("state") not in ("unknown", "unavailable", None):
        return data["state"]
    return default

DRY_RUN = False  # Wird in main() gesetzt

def ha_set_number(entity_id: str, value: float) -> bool:
    """Setzt einen number-Entity-Wert."""
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
        log.error("HA SET %s Fehler: %s", entity_id, e)
        return False

def ha_switch(entity_id: str, turn_on: bool) -> bool:
    """Schaltet einen switch-Entity."""
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
        log.error("HA SWITCH %s Fehler: %s", entity_id, e)
        return False

# ---------------------------------------------------------------------------
# Sonnenauf- und Sonnenuntergang aus HA
# ---------------------------------------------------------------------------
def get_sun_state() -> dict:
    """Gibt Sonnenauf-/untergang und aktuellen Status zurück."""
    data = ha_get("sun.sun")
    if data:
        attrs = data.get("attributes", {})
        return {
            "state": data.get("state"),  # "above_horizon" oder "below_horizon"
            "rising": attrs.get("rising", False),
            "next_rising": attrs.get("next_rising"),
            "next_setting": attrs.get("next_setting"),
        }
    return {"state": "unknown"}

# ---------------------------------------------------------------------------
# Zustandsspeicher (persistent über Zyklen)
# ---------------------------------------------------------------------------
STATE_PATH = "/data/controller_state.json"

def load_state() -> dict:
    try:
        if Path(STATE_PATH).exists():
            with open(STATE_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "pi_integral": 0.0,
        "grid_p_filtered": 0.0,
        "solar_p_last": 0.0,
        "haus_p_last": 0.0,
        "last_gs": 0.0,
        "last_calibration_ts": 0.0,
        "active_mode": "night",  # "night", "active", "calibration"
    }

def save_state(state: dict):
    try:
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log.error("State speichern Fehler: %s", e)

# ---------------------------------------------------------------------------
# Asymmetrischer Tiefpassfilter
# ---------------------------------------------------------------------------
def asymmetric_filter(raw: float, last: float) -> float:
    """
    Selbstheilend: Bei Sprung >300W sofort auf echten Wert.
    Netzbezug (raw < -30): schnelle Reaktion 70/30.
    Sonst: langsame Reaktion 15/85.
    """
    if abs(raw - last) > 300:
        return round(raw, 1)
    elif raw < -30:
        return round(last * 0.30 + raw * 0.70, 1)
    else:
        return round(last * 0.85 + raw * 0.15, 1)

# ---------------------------------------------------------------------------
# PI-Regler
# ---------------------------------------------------------------------------
def calc_kp(error: float) -> float:
    """Dynamisches kP abhängig von der Fehlergröße."""
    abs_err = abs(error)
    if abs_err > 200:
        return 0.5
    elif abs_err > 50:
        return 0.2
    else:
        return 0.08

def pi_step(
    error: float,
    last_integral: float,
    dt: float,
    ki: float,
    i_limit: float,
    in_deadband: bool,
    tag_modus: bool,
) -> tuple[float, float]:
    """
    Einen PI-Regler-Schritt berechnen.
    Gibt (output, new_integral) zurück.
    """
    # Integral update
    if in_deadband:
        # Im Deadband: Integral langsam abbauen
        decay = 0.97 if tag_modus else 0.90
        new_integral = last_integral * decay
    elif abs(error) > 20:
        new_integral = last_integral + ki * error * dt
    else:
        new_integral = last_integral * 0.97

    # Anti-Windup
    anti_windup_ok = (
        (-i_limit < new_integral < i_limit)
        or (new_integral <= -i_limit and error > 0)
        or (new_integral >= i_limit and error < 0)
    )
    if not anti_windup_ok:
        new_integral = last_integral

    # Begrenzen
    new_integral = max(-i_limit, min(i_limit, new_integral))

    kp = calc_kp(error)
    output = kp * error + new_integral

    return round(output, 2), round(new_integral, 2)

# ---------------------------------------------------------------------------
# Rate-Limiting
# ---------------------------------------------------------------------------
def apply_rate_limit(
    target: float,
    last_gs: float,
    grid_p: float,
    solar_delta: float,
    haus_delta: float,
    tag_modus: bool,
) -> float:
    delta = target - last_gs

    # Schnelle Sprünge → kein Limit
    if abs(solar_delta) > 150 or abs(haus_delta) > 200:
        rate_limit = 2400
    elif delta < 0 and grid_p < -30:
        rate_limit = 2400
    elif tag_modus:
        rate_limit = 200 if abs(grid_p) > 300 else 100
    elif delta > 0:
        rate_limit = 200
    else:
        rate_limit = 2400

    if abs(delta) > rate_limit:
        return last_gs + rate_limit * (1 if delta > 0 else -1)
    return target

# ---------------------------------------------------------------------------
# HMS-Drosselung
# ---------------------------------------------------------------------------
def calc_hms_limits(
    solar_p_2000: float,
    solar_p_1600: float,
    hms_1600_online: bool,
    curr_soc: float,
    grid_p: float,
    haus_p: float,
    hms_throttle_soc: float,
    tag_modus: bool,
) -> tuple[float, float]:
    """
    Berechnet HMS-2000 und HMS-1600 Limits.
    Ab hms_throttle_soc % wird gedrosselt.
    """
    max_2000 = 2000.0
    max_1600 = 1600.0

    if not tag_modus:
        # Nacht: volle Leistung freigeben (HMS schlafen sowieso)
        return max_2000, max_1600

    total = solar_p_2000 + solar_p_1600
    if total > 50:
        anteil_2000 = solar_p_2000 / total
    else:
        anteil_2000 = 1.0 if not hms_1600_online else 0.5

    if curr_soc >= hms_throttle_soc:
        # Drosseln: Zielleistung = aktueller Bedarf
        target = solar_p_2000 + solar_p_1600 + grid_p
        min_limit = max(haus_p, 100.0)
        target = max(min_limit, min(target, 3600.0))

        limit_2000 = min(round(target * anteil_2000), max_2000)
        limit_1600 = min(round(target * (1 - anteil_2000)), max_1600)
    else:
        # Volle Leistung
        limit_2000 = max_2000
        limit_1600 = max_1600

    return limit_2000, limit_1600

# ---------------------------------------------------------------------------
# Hauptregelschleife
# ---------------------------------------------------------------------------
TICK_S = 5  # Regelzyklus in Sekunden

def main():
    global DRY_RUN
    log.info("SunEnergy XT Controller startet...")
    opts = load_options()
    state = load_state()

    DRY_RUN = bool(opts.get("dry_run", True))
    if DRY_RUN:
        log.info("DRY-RUN Modus aktiv - es wird NICHTS in HA geschrieben!")
    else:
        log.info("Aktiver Modus - Controller schreibt in HA")

    # Konfiguration
    grid_sensor    = opts["grid_sensor"]
    soc_sensor     = opts["soc_sensor"]
    gs_entity      = opts["gs_entity"]
    mm_switch      = opts["mm_switch"]
    sa_entity      = opts["sa_entity"]
    hms_2000_entity = opts["hms_2000_entity"]
    hms_1600_entity = opts["hms_1600_entity"]
    soc_normal_max = float(opts["soc_normal_max"])   # 95%
    soc_min        = float(opts["soc_min"])           # 10%
    hms_throttle   = float(opts["hms_throttle_soc"]) # 90%
    calib_days     = float(opts["calibration_days"]) # 15
    ki             = float(opts["ki"])                # 0.005
    i_limit        = float(opts["i_limit"])           # 150

    # Deadband Grenzen
    DEADBAND_HIGH  =  50.0   # W
    DEADBAND_LOW_D = -50.0   # W tagsüber
    DEADBAND_LOW_N = -80.0   # W nachts
    SURPLUS_THRESHOLD = 0.0  # Shelly negativ = Überschuss

    log.info("Konfiguration geladen: SOC max=%s%%, min=%s%%, HMS Drossel=%s%%",
             soc_normal_max, soc_min, hms_throttle)

    # SA auf Normalwert setzen beim Start
    ha_set_number(sa_entity, soc_normal_max)

    while True:
        try:
            tick_start = time.monotonic()

            # ------------------------------------------------------------------
            # 1. Messwerte lesen
            # ------------------------------------------------------------------
            grid_p_raw_str = ha_get_state(grid_sensor, "0")
            soc_str        = ha_get_state(soc_sensor, "0")
            gs_last_str    = ha_get_state(gs_entity, "0")

            # Validierung
            try:
                grid_p_raw = float(grid_p_raw_str)
                curr_soc   = float(soc_str)
                last_gs    = float(gs_last_str)
                data_valid = True
            except (TypeError, ValueError):
                data_valid = False
                grid_p_raw = 0.0
                curr_soc = 0.0
                last_gs = state["last_gs"]

            # Watchdog: Shelly Timestamp prüfen
            shelly_data = ha_get(grid_sensor)
            if shelly_data:
                last_upd = shelly_data.get("last_updated", "")
                try:
                    upd_ts = datetime.fromisoformat(
                        last_upd.replace("Z", "+00:00")
                    ).timestamp()
                    watchdog_ok = (time.time() - upd_ts) < 60
                except Exception:
                    watchdog_ok = False
            else:
                watchdog_ok = False

            # ------------------------------------------------------------------
            # 2. Sicherheits-Stopp
            # ------------------------------------------------------------------
            if not watchdog_ok or not data_valid:
                log.warning("Sicherheits-Stopp! watchdog=%s data_valid=%s",
                            watchdog_ok, data_valid)
                # MM AN (Gerät regelt selbst), GS=0
                ha_switch(mm_switch, True)
                ha_set_number(gs_entity, 0)
                state["grid_p_filtered"] = grid_p_raw
                save_state(state)
                time.sleep(TICK_S)
                continue

            # ------------------------------------------------------------------
            # 3. HMS Leistungen lesen
            # ------------------------------------------------------------------
            solar_p_2000 = abs(float(ha_get_state(
                "sensor.hoymiles_hms_2000_4t_power", "0") or 0))
            solar_p_1600 = abs(float(ha_get_state(
                "sensor.hoymiles_hms_1600_4t_power", "0") or 0))
            hms_1600_reachable = ha_get_state(
                "binary_sensor.hoymiles_hms_1600_4t_reachable", "off")
            hms_1600_online = hms_1600_reachable == "on"

            solar_p = solar_p_2000 + solar_p_1600
            solar_delta = solar_p - state["solar_p_last"]

            # Hausverbrauch
            haus_p = abs(float(ha_get_state(
                "sensor.hausverbrauch_aktuell", "0") or 0))
            haus_delta = haus_p - state["haus_p_last"]

            # ------------------------------------------------------------------
            # 4. Filter anwenden
            # ------------------------------------------------------------------
            grid_p = asymmetric_filter(grid_p_raw, state["grid_p_filtered"])

            # ------------------------------------------------------------------
            # 5. Sonnenstand und Modus bestimmen
            # ------------------------------------------------------------------
            sun = get_sun_state()
            sun_above = sun["state"] == "above_horizon"

            # Tag-Modus: Sonne über Horizont UND echter Überschuss vorhanden
            # (Shelly negativ = mehr Produktion als Verbrauch)
            ueberschuss_vorhanden = grid_p < SURPLUS_THRESHOLD
            tag_modus = sun_above and ueberschuss_vorhanden

            # ------------------------------------------------------------------
            # 6. Zwangsladung prüfen (alle calibration_days Tage)
            # ------------------------------------------------------------------
            tage_seit = (time.time() - state["last_calibration_ts"]) / 86400
            # Zwangsladung bei Sonnenuntergang triggern
            zwangsladung_nötig = (
                tage_seit > calib_days
                and not sun_above  # Sonne ist weg
                and curr_soc < 100
            )

            # ------------------------------------------------------------------
            # 7. Zwangsladung aktiv?
            # ------------------------------------------------------------------
            if zwangsladung_nötig:
                log.info("Zwangsladung! %s Tage seit letzter Vollladung, SOC=%s%%",
                         round(tage_seit, 1), curr_soc)
                # SA auf 100% setzen
                ha_set_number(sa_entity, 100)
                # MM AUS, wir steuern
                ha_switch(mm_switch, False)
                # Maximale Ladeleistung
                ha_set_number(gs_entity, -2400)
                state["active_mode"] = "calibration"
                save_state(state)
                time.sleep(TICK_S)
                continue

            # Zwangsladung beendet wenn SOC=100
            if state["active_mode"] == "calibration" and curr_soc >= 100:
                log.info("Zwangsladung abgeschlossen! SOC=100%%")
                state["last_calibration_ts"] = time.time()
                state["active_mode"] = "night"
                # SA zurück auf Normalwert
                ha_set_number(sa_entity, soc_normal_max)
                # MM AN
                ha_switch(mm_switch, True)
                ha_set_number(gs_entity, 0)
                save_state(state)
                time.sleep(TICK_S)
                continue

            # ------------------------------------------------------------------
            # 8. Nachtmodus (kein Überschuss oder Sonne weg)
            # ------------------------------------------------------------------
            if not tag_modus:
                # MM AN, GS=0 — Gerät regelt selbst
                ha_switch(mm_switch, True)
                ha_set_number(gs_entity, 0)
                # Integral langsam abbauen
                state["pi_integral"] *= 0.90
                state["active_mode"] = "night"
                state["grid_p_filtered"] = grid_p
                state["solar_p_last"] = solar_p
                state["haus_p_last"] = haus_p
                log.debug("Nacht/kein Überschuss: MM=AN, GS=0, SOC=%.1f%%", curr_soc)
                save_state(state)
                time.sleep(TICK_S)
                continue

            # ------------------------------------------------------------------
            # 9. Aktive Regelung (Tag, Überschuss vorhanden)
            # ------------------------------------------------------------------
            state["active_mode"] = "active"

            # MM AUS — wir übernehmen die Regelung
            ha_switch(mm_switch, False)

            # Deadband bestimmen
            deadband_low = DEADBAND_LOW_D  # tagsüber
            if grid_p > DEADBAND_HIGH:
                deadband = "import"
            elif grid_p < deadband_low:
                deadband = "export"
            else:
                deadband = "neutral"

            in_deadband = deadband == "neutral"

            # Fehler für PI-Regler
            error = grid_p if not in_deadband else 0.0

            # Feedforward
            ff_solar = round(-solar_delta) if abs(solar_delta) > 150 else 0
            ff_haus  = round(haus_delta)   if abs(haus_delta)  > 200 else 0
            feedforward = ff_solar + ff_haus

            # PI-Schritt
            pi_out, new_integral = pi_step(
                error=error,
                last_integral=state["pi_integral"],
                dt=TICK_S,
                ki=ki,
                i_limit=i_limit,
                in_deadband=in_deadband,
                tag_modus=True,
            )

            # GS-Sollwert berechnen
            if curr_soc <= soc_min:
                # SOC zu niedrig — nicht entladen
                r_target = max(min(last_gs, 0), -10)
            elif deadband == "import":
                r_target = max(last_gs + pi_out + feedforward, 0)
                r_target = min(r_target, 2400)
            elif deadband == "export" and curr_soc < soc_normal_max:
                r_target = min(last_gs + pi_out + feedforward, -10)
                r_target = max(r_target, -2400)
            elif deadband == "export" and curr_soc >= soc_normal_max:
                r_target = 0
            else:
                r_target = last_gs

            # Rate-Limiting
            final_gs = apply_rate_limit(
                target=r_target,
                last_gs=last_gs,
                grid_p=grid_p,
                solar_delta=solar_delta,
                haus_delta=haus_delta,
                tag_modus=True,
            )
            final_gs = round(final_gs)

            # Schreibschwelle: nur schreiben wenn Änderung > 50W tagsüber
            delta_gs = abs(final_gs - last_gs)
            if delta_gs >= 50:
                ha_set_number(gs_entity, final_gs)
                log.info(
                    "GS=%dW | grid=%.1fW | SOC=%.1f%% | err=%.1fW | int=%.2f | "
                    "dead=%s | ff=%dW",
                    final_gs, grid_p, curr_soc, error, new_integral,
                    deadband, feedforward,
                )

            # ------------------------------------------------------------------
            # 10. HMS-Drosselung
            # ------------------------------------------------------------------
            limit_2000, limit_1600 = calc_hms_limits(
                solar_p_2000=solar_p_2000,
                solar_p_1600=solar_p_1600,
                hms_1600_online=hms_1600_online,
                curr_soc=curr_soc,
                grid_p=grid_p,
                haus_p=haus_p,
                hms_throttle_soc=hms_throttle,
                tag_modus=True,
            )

            # Nur schreiben wenn Änderung > 50W
            curr_limit_2000 = float(ha_get_state(hms_2000_entity, "2000") or 2000)
            if abs(curr_limit_2000 - limit_2000) >= 50:
                ha_set_number(hms_2000_entity, limit_2000)
                log.info("HMS-2000 Limit: %dW", limit_2000)

            if hms_1600_online:
                curr_limit_1600 = float(
                    ha_get_state(hms_1600_entity, "1600") or 1600)
                if abs(curr_limit_1600 - limit_1600) >= 50:
                    ha_set_number(hms_1600_entity, limit_1600)
                    log.info("HMS-1600 Limit: %dW", limit_1600)

            # ------------------------------------------------------------------
            # 11. Vollladung erkennen und Zeitstempel speichern
            # ------------------------------------------------------------------
            if curr_soc >= 100:
                state["last_calibration_ts"] = time.time()
                log.info("Vollladung erkannt, Zeitstempel gespeichert.")

            # ------------------------------------------------------------------
            # 12. State speichern
            # ------------------------------------------------------------------
            state["pi_integral"]      = new_integral
            state["grid_p_filtered"]  = grid_p
            state["solar_p_last"]     = solar_p
            state["haus_p_last"]      = haus_p
            state["last_gs"]          = final_gs
            save_state(state)

        except Exception as e:
            log.error("Unerwarteter Fehler im Regelzyklus: %s", e, exc_info=True)

        # Zyklus-Timing
        elapsed = time.monotonic() - tick_start
        sleep_time = max(0, TICK_S - elapsed)
        time.sleep(sleep_time)


if __name__ == "__main__":
    main()

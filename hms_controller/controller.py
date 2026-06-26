import os
import json
import time
import logging
import signal
import requests

# Options Path and default configuration
OPTIONS_PATH = "/data/options.json"
DEFAULT_OPTIONS = {
    "shelly_ip": "192.168.178.98",
    "ha_ip": "192.168.178.132",
    "hms_2000_entity": "number.hoymiles_hms_2000_4t_limit_nonpersistent_absolute",
    "hms_1600_entity": "number.hoymiles_hms_1600_4t_limit_nonpersistent_absolute",
    "grid_sensor": "sensor.shellypro3em_leistung",
    "hms_2000_power_sensor": "sensor.hoymiles_hms_2000_4t_power",
    "hms_1600_power_sensor": "sensor.hoymiles_hms_1600_4t_power",
    "soc_sensor": "sensor.sunenergyxt_500_pro_system_speicherlevel",
    "soc_sensor_l2": "sensor.sunenergyxt_500_pro_l2_system_speicherlevel",
    "sunenergy_ip": "192.168.178.94",
    "sunenergy_ip_l2": "192.168.178.122",
    "damping": 0.5,
    "hms_min": 300,
    "hms_max": 3600,
    "tick_interval": 5
}

def load_options() -> dict:
    if os.path.exists(OPTIONS_PATH):
        try:
            with open(OPTIONS_PATH, "r") as f:
                opts = json.load(f)
                return {**DEFAULT_OPTIONS, **opts}
        except Exception as e:
            print(f"Error loading options: {e}")
    return DEFAULT_OPTIONS

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger("HMSController")

# Load configuration for HA client init
opts = load_options()
HA_TOKEN = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN", "")
if os.environ.get("SUPERVISOR_TOKEN"):
    HA_URL = "http://supervisor/core"
else:
    ha_ip = opts.get("ha_ip", "192.168.178.132")
    HA_URL = f"http://{ha_ip}:8123"

HA_SESSION = requests.Session()
HA_SESSION.headers.update({"Authorization": f"Bearer {HA_TOKEN}"})
DEV_SESSION = requests.Session()

def ha_get_state(entity_id: str, default=None):
    if not HA_TOKEN:
        log.debug(f"No HA Token configured, returning default for {entity_id}")
        return default
    try:
        r = HA_SESSION.get(f"{HA_URL}/api/states/{entity_id}", timeout=3)
        if r.status_code == 200:
            val = r.json().get("state")
            if val not in ("unknown", "unavailable", None):
                return val
    except Exception as e:
        log.error(f"HA GET {entity_id} failed: {e}")
    return default

def ha_set_number(entity_id: str, value: float) -> bool:
    val_rounded = round(value)
    if not HA_TOKEN:
        log.info(f"🔍 [MOCK-SET] Would set HA entity {entity_id} to {val_rounded}")
        return True
    try:
        r = HA_SESSION.post(
            f"{HA_URL}/api/services/number/set_value",
            json={"entity_id": entity_id, "value": val_rounded},
            timeout=3
        )
        if r.status_code not in (200, 201):
            log.error(f"HA SET {entity_id} failed: status={r.status_code}, response={r.text}")
            return False
        return True
    except Exception as e:
        log.error(f"HA SET {entity_id} failed: {e}")
        return False

def shelly_direct_power(ip: str):
    try:
        r = DEV_SESSION.get(f"http://{ip}/rpc/EM.GetStatus?id=0", timeout=2)
        if r.status_code == 200:
            val = r.json().get("total_act_power")
            if val is not None:
                return float(val)
    except Exception as e:
        log.debug(f"Shelly direct read from {ip} failed: {e}")
    return None

def get_grid_power(shelly_ip: str, grid_sensor: str) -> tuple[float, str]:
    # Primary: Shelly direct
    val = shelly_direct_power(shelly_ip)
    if val is not None:
        return val, "Shelly direct"
    
    # Secondary: HA sensor fallback
    ha_val = ha_get_state(grid_sensor)
    if ha_val is not None:
        try:
            return float(ha_val), "HA sensor"
        except (ValueError, TypeError):
            pass
            
    return 0.0, "default (0W)"

def get_sunenergy_op(ip: str) -> float:
    if not ip:
        return 0.0
    try:
        r = DEV_SESSION.get(f"http://{ip}/read", timeout=2)
        if r.status_code == 200:
            return float(r.json().get("state", {}).get("reported", {}).get("OP", 0.0))
    except Exception as e:
        log.debug(f"SunEnergyXT direct read from {ip} failed: {e}")
    return 0.0

STATE_PATH = "/data/controller_state.json"

def save_state(state_data: dict):
    try:
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        with open(STATE_PATH, "w") as f:
            json.dump(state_data, f, indent=2)
    except Exception as e:
        log.error(f"Failed to save state: {e}")

def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "hms_limit_last": 3600.0,
        "last_written_2000": 2000.0,
        "last_written_1600": 1600.0,
        "logs": [],
        "grid_trend": []
    }

RUNNING = True

def handle_term(signum, frame):
    global RUNNING
    log.info("Shutdown signal received. Exiting...")
    RUNNING = False

def main():
    global RUNNING
    signal.signal(signal.SIGTERM, handle_term)
    signal.signal(signal.SIGINT, handle_term)
    
    log.info("HMS Zero Feed-in Controller main loop started.")
    
    state = load_state()
    hms_limit_last = state.get("hms_limit_last", 3600.0)
    last_written_2000 = state.get("last_written_2000", 2000.0)
    last_written_1600 = state.get("last_written_1600", 1600.0)
    logs = state.get("logs", [])
    grid_trend = state.get("grid_trend", [])
    
    tick_count = 0
    
    while RUNNING:
        opts = load_options()
        
        shelly_ip = opts["shelly_ip"]
        hms_2000_entity = opts["hms_2000_entity"]
        hms_1600_entity = opts["hms_1600_entity"]
        grid_sensor = opts["grid_sensor"]
        hms_2000_power_sensor = opts["hms_2000_power_sensor"]
        hms_1600_power_sensor = opts["hms_1600_power_sensor"]
        soc_sensor = opts.get("soc_sensor")
        soc_sensor_l2 = opts.get("soc_sensor_l2")
        sunenergy_ip = opts.get("sunenergy_ip")
        sunenergy_ip_l2 = opts.get("sunenergy_ip_l2")
        damping = opts.get("damping", 0.5)
        hms_min = opts.get("hms_min", 300)
        hms_max = opts.get("hms_max", 3600)
        tick_interval = opts.get("tick_interval", 5)
        
        # 1. Read Grid Power
        grid_p, grid_source = get_grid_power(shelly_ip, grid_sensor)
        
        # Keep trend (last 20 values)
        grid_trend.append(grid_p)
        if len(grid_trend) > 20:
            grid_trend.pop(0)
            
        # 2. Adjust HMS total limit
        delta = grid_p * damping
        hms_limit_new = hms_limit_last + delta
        hms_limit_new = max(hms_min, min(hms_max, hms_limit_new))
        
        # 3. Read current HMS power
        power_2000_raw = ha_get_state(hms_2000_power_sensor)
        power_1600_raw = ha_get_state(hms_1600_power_sensor)
        
        # Convert to float safely
        power_2000 = 0.0
        if power_2000_raw is not None:
            try:
                power_2000 = max(0.0, float(power_2000_raw))
            except ValueError:
                pass
            
        power_1600 = 0.0
        if power_1600_raw is not None:
            try:
                power_1600 = max(0.0, float(power_1600_raw))
            except ValueError:
                pass
            
        total_power = power_2000 + power_1600
        
        # 4. Proportional splitting logic including edge cases
        if power_2000 == 0 and power_1600 == 0:
            # Beide 0W (nachts) -> beide auf hms_min (Standard: 300W)
            limit_2000 = hms_min
            limit_1600 = hms_min
            ratio_2000 = 0.5
            ratio_1600 = 0.5
        elif power_2000 == 0:
            # HMS-2000 offline/0W -> bekommt 10W, HMS-1600 bekommt 100% des Soll-Limits
            limit_2000 = 10
            limit_1600 = max(10, hms_limit_new)
            ratio_2000 = 0.0
            ratio_1600 = 1.0
        elif power_1600 == 0:
            # HMS-1600 offline/0W -> bekommt 10W, HMS-2000 bekommt 100% des Soll-Limits
            limit_2000 = max(10, hms_limit_new)
            limit_1600 = 10
            ratio_2000 = 1.0
            ratio_1600 = 0.0
        else:
            # Proportional zur aktuellen IST-Leistung
            ratio_2000 = power_2000 / total_power
            ratio_1600 = power_1600 / total_power
            limit_2000 = max(10, hms_limit_new * ratio_2000)
            limit_1600 = max(10, hms_limit_new * ratio_1600)
            
        # Round to integers
        limit_2000_rounded = int(round(limit_2000))
        limit_1600_rounded = int(round(limit_1600))
        
        # 5. Determine whether we need to set values in HA
        tick_count += 1
        is_heartbeat = (tick_count % 6 == 0)
        
        def should_send(new_val, last_val):
            if last_val is None:
                return True
            if abs(new_val - last_val) >= 10:
                return True
            if new_val in (10, hms_min, hms_max) and last_val != new_val:
                return True
            if is_heartbeat:
                return True
            return False
            
        if should_send(limit_2000_rounded, last_written_2000):
            if ha_set_number(hms_2000_entity, limit_2000_rounded):
                last_written_2000 = limit_2000_rounded
                
        if should_send(limit_1600_rounded, last_written_1600):
            if ha_set_number(hms_1600_entity, limit_1600_rounded):
                last_written_1600 = limit_1600_rounded
                
        # 6. Read other status values for Web UI
        soc_l1 = 0.0
        if soc_sensor:
            soc_l1_val = ha_get_state(soc_sensor)
            if soc_l1_val is not None:
                try:
                    soc_l1 = float(soc_l1_val)
                except ValueError:
                    pass
                
        soc_l2 = 0.0
        if soc_sensor_l2:
            soc_l2_val = ha_get_state(soc_sensor_l2)
            if soc_l2_val is not None:
                try:
                    soc_l2 = float(soc_l2_val)
                except ValueError:
                    pass
                
        se_l1_op = get_sunenergy_op(sunenergy_ip)
        se_l2_op = get_sunenergy_op(sunenergy_ip_l2)
        
        # 7. Log regulation step
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp_str} | Grid={grid_p:+.1f}W ({grid_source}) | Target={hms_limit_new:.0f}W | HMS2000={power_2000:.0f}W (Lim={limit_2000_rounded}W, R={ratio_2000*100:.1f}%) | HMS1600={power_1600:.0f}W (Lim={limit_1600_rounded}W, R={ratio_1600*100:.1f}%)"
        log.info(log_entry)
        
        logs.append(log_entry)
        if len(logs) > 20:
            logs.pop(0)
            
        # Update state dict
        current_state = {
            "timestamp": time.time(),
            "grid_power": grid_p,
            "grid_source": grid_source,
            "grid_trend": grid_trend,
            "hms_2000": {
                "power": power_2000,
                "limit": limit_2000_rounded,
                "ratio": ratio_2000
            },
            "hms_1600": {
                "power": power_1600,
                "limit": limit_1600_rounded,
                "ratio": ratio_1600
            },
            "soc_l1": soc_l1,
            "soc_l2": soc_l2,
            "se_l1_op": se_l1_op,
            "se_l2_op": se_l2_op,
            "hms_limit_last": hms_limit_new,
            "last_written_2000": last_written_2000,
            "last_written_1600": last_written_1600,
            "logs": logs
        }
        
        save_state(current_state)
        hms_limit_last = hms_limit_new
        
        # Sleep for tick_interval in 0.5s steps to respond fast to SIGTERM
        end_time = time.monotonic() + tick_interval
        while RUNNING and time.monotonic() < end_time:
            time.sleep(0.5)

if __name__ == "__main__":
    main()

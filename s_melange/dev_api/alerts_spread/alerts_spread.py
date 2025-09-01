from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from urllib.parse import unquote
from common.config import get_redis_client
import datetime, time, threading, uuid, json, re
from common.trading_hours import TradingHours
from common.my_logger import logger
from pathlib import Path
from pydantic import BaseModel
from typing import Literal

router = APIRouter(prefix="/alerts2", tags=["alerts-api"])
redis_client = get_redis_client()
alerts_key = "alerts_spread"
tree_alerts_key = "tree_alerts"
group_alerts_key = "group_alerts"
trading_hour = TradingHours(start_buffer=60)
BASE_DIR = Path(__file__).resolve().parent

OPERATORS = {
    '<': lambda a, b: a < b,
    '=': lambda a, b: a == b,
    '>': lambda a, b: a > b
}

def get_redis_key():
    return f"tick:{(datetime.date.today()-datetime.timedelta(days=0)).strftime('%Y%m%d')}"

@router.get("/test")
def read_root():
    return {"message": "Hello, Alerts Spread!"}

@router.get("/play-alert")
def play_alert():
    return FileResponse(BASE_DIR / "alert.mp3", media_type='audio/mp3')

@router.get("/symbols")
def get_symbols():
    symbols = redis_client.hkeys(get_redis_key())
    exchanges = {}
    for symbol in symbols:
        if ":" in symbol:
            exchange, sym = symbol.split(":", 1)
            if exchange not in exchanges:
                exchanges[exchange] = {}
            if exchange in ("NSE", "BSE"):
                exchanges[exchange].setdefault("symbols", []).append(sym)
                continue
            try:
                match = re.match(r"^([A-Z]+)(\d.{4})(.*)(..)$", sym)
                if not match:
                    continue
                symbol_part, exp_str, strike, opt_type = match.groups()
                exchanges[exchange].setdefault(symbol_part, {}).setdefault(exp_str, {}).setdefault(strike, []).append(opt_type)
            except Exception as e:
                logger.warning(f"Error parsing {sym}: {e}")
    return exchanges

@router.get("/tick-data/{symbol}")
def get_tick_data(symbol: str):
    symbol = unquote(symbol).upper().strip()
    data = redis_client.hget(get_redis_key(), symbol)
    if data:
        return json.loads(data)
    raise HTTPException(status_code=404, detail="Symbol not found")


# ---------- Tree Alerts ----------

@router.post("/tree")
def add_tree_alert(data: dict):
    required_keys = {'symbol', 'qty', 'operator', 'target', 'path'}
    if not required_keys.issubset(data.keys()):
        raise HTTPException(status_code=400, detail="Missing required fields")

    alert_id = str(uuid.uuid4())
    symbol = data['symbol'].upper().strip()
    qty = data.get("qty", 1)

    tick_data = redis_client.hget(get_redis_key(), symbol)
    if not tick_data:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {symbol}")

    last_price = json.loads(tick_data).get("last_price", 0)

    alert_data = {
        "id": alert_id,
        "symbol": symbol,
        "qty": qty,
        "operator": data["operator"],
        "target": float(data["target"]),
        "status": "Active",
        "path": data["path"],
        "last_price": last_price,
        "timestamp": datetime.datetime.now().isoformat()
    }

    redis_client.hset(tree_alerts_key, alert_id, json.dumps(alert_data))
    return {"id": alert_id}

@router.get("/tree")
def get_tree_alerts():
    alerts_data = redis_client.hgetall(tree_alerts_key)
    return {k: json.loads(v) for k, v in alerts_data.items()}

@router.delete("/tree/{alert_id}")
def delete_tree_alert(alert_id: str):
    if redis_client.hdel(tree_alerts_key, alert_id):
        return {"message": "Tree alert deleted"}
    raise HTTPException(status_code=404, detail="Alert not found")

@router.post("/tree/{alert_id}/ack")
def acknowledge_tree_alert(alert_id: str):
    alert_json = redis_client.hget(tree_alerts_key, alert_id)
    if not alert_json:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert = json.loads(alert_json)
    alert["status"] = "Acknowledged"
    redis_client.hset(tree_alerts_key, alert_id, json.dumps(alert))
    return {"message": "Alert acknowledged"}

@router.post("/tree/{alert_id}/reset")
def reset_tree_alert(alert_id: str):
    alert_json = redis_client.hget(tree_alerts_key, alert_id)
    if not alert_json:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert = json.loads(alert_json)
    if alert['status'] != 'Acknowledged':
        raise HTTPException(status_code=400, detail="Only acknowledged alerts can be reset")
    alert["status"] = "Active"
    alert["timestamp"] = datetime.datetime.now().isoformat()
    redis_client.hset(tree_alerts_key, alert_id, json.dumps(alert))
    return {"message": "Alert reset to Active"}


# ---------- Group Alerts ----------

class GroupTarget(BaseModel):
    operator: Literal["<", ">"]
    target: float
    status: Literal["Pending", "Active", "Triggered", "Acknowledged"]


@router.get("/group-targets")
def get_group_targets():
    all_data = redis_client.hgetall(group_alerts_key)
    results = {}

    for group_name_bytes, value_bytes in all_data.items():
        group_name = group_name_bytes.decode()
        value = value_bytes.decode()
        try:
            results[group_name] = json.loads(value)
        except json.JSONDecodeError:
            continue

    return results


@router.get("/group-targets/{group}")
def get_group_target(group: str):
    data = redis_client.hget(group_alerts_key, group)
    if not data:
        return JSONResponse(status_code=404, content={"message": "Group target not found"})
    return json.loads(data)


@router.post("/group-targets/{group}")
def set_group_target(group: str, target: GroupTarget):
    redis_client.hset(group_alerts_key, group, target.json())
    return {"message": "Group target set", "group": group, "data": target}


@router.delete("/group-targets/{group}")
def delete_group_target(group: str):
    redis_client.hdel(group_alerts_key, group)
    return {"message": "Group target deleted", "group": group}


# ---------- Background Monitor ----------
def monitor_alerts():
    while True:
        # 1. Process Leaf Alerts
        alerts_data = redis_client.hgetall(tree_alerts_key)

        for alert_id, raw in alerts_data.items():
            alert = json.loads(raw)

            if alert.get("status") in ("Triggered", "Acknowledged"):
                continue

            symbol = alert.get("symbol")
            if not symbol:
                continue

            tick = redis_client.hget(get_redis_key(), symbol)
            if not tick:
                continue

            tick_data = json.loads(tick)
            last_price = tick_data.get("last_price", 0)
            alert["last_price"] = last_price

            if OPERATORS[alert["operator"]](last_price, alert["target"]):
                alert["status"] = "Triggered"

            redis_client.hset(tree_alerts_key, alert_id, json.dumps(alert))

        # 2. Process Group Alerts
        group_keys = redis_client.hkeys(group_alerts_key)

        for group_name in group_keys:

            raw = redis_client.hget(group_alerts_key, group_name)
            if not raw:
                continue

            group_alert = json.loads(raw)

            if group_alert.get("status") in ("Triggered", "Acknowledged"):
                continue

            total = 0
            alerts_data = redis_client.hgetall(tree_alerts_key)

            for alert_id, alert_json in alerts_data.items():
                alert = json.loads(alert_json)
                if alert.get("path", [])[0] == group_name:
                    qty = float(alert.get("qty", 0))
                    price = float(alert.get("last_price", 0))
                    total += qty * price

            operator = group_alert.get("operator")
            target = group_alert.get("target")

            if operator and target and OPERATORS[operator](total, target):
                group_alert["status"] = "Triggered"

            redis_client.hset(group_alerts_key, group_name, json.dumps(group_alert))

        # Sleep logic based on trading hours
        if not trading_hour.is_open():
            seconds_until_open = trading_hour.time_until_next_open().total_seconds()
            logger.info(f"[Alerts] Market closed. Sleeping for {seconds_until_open // 60:.1f} min.")
            time.sleep(seconds_until_open)
        else:
            time.sleep(2)


# Start background thread
threading.Thread(target=monitor_alerts, daemon=True).start()
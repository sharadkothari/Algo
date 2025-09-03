from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from urllib.parse import unquote
from common.config import get_redis_client
import datetime,  uuid, json, re
from common.trading_hours import TradingHours
from common.my_logger import logger
from pathlib import Path
from typing import Optional, Literal
from pydantic import BaseModel

class GroupTarget(BaseModel):
    operator: Optional[Literal["<", "=", ">"]] = None
    target: Optional[float] = None
    status: Literal["Pending", "Active", "Triggered", "Acknowledged"]


router = APIRouter(prefix="/alerts2", tags=["alerts-api"])
redis_client = get_redis_client()
alerts_key = "alerts_spread"
tree_alerts_key = "tree_alerts"
group_alerts_key = "group_alerts"
group_leaves_prefix = "group_leaves:"
groups_order_key = "groups_order"
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
    alerts = {k: json.loads(v) for k, v in alerts_data.items()}

    group_targets_data = redis_client.hgetall(group_alerts_key)
    group_targets = {k: json.loads(v) for k, v in group_targets_data.items()}

    order = redis_client.lrange(groups_order_key, 0, -1)
    ordered_groups = [g for g in order]
    all_groups_set = set(group_targets.keys()) | {alert["path"][0] for alert in alerts.values() if "path" in alert}
    missing = sorted(all_groups_set - set(ordered_groups))
    ordered_groups.extend(missing)
    all_groups = ordered_groups

    result = []
    for group in all_groups:
        # Build group row
        target_data = group_targets.get(group, {"operator": "", "target": None, "status": "Pending"})
        group_row = {
            "id": f"group-{group}",
            "groupName": group,
            "operator": target_data.get("operator", ""),
            "target": target_data.get("target"),
            "status": target_data.get("status", "Pending"),
            "path": [group],
            "symbol": group,  # For auto-group display
        }
        result.append(group_row)

        # Get ordered leaves
        order_key = f"{group_leaves_prefix}{group}"
        ids = redis_client.lrange(order_key, 0, -1)
        group_leaves = []
        seen_ids = set()
        for id_b in ids:
            aid = id_b
            if aid in alerts and aid not in seen_ids:
                leaf = alerts[aid]
                leaf["id"] = aid  # Ensure ID is set
                group_leaves.append(leaf)
                seen_ids.add(aid)

        # Append any unsorted/missing leaves (fallback), sort by timestamp, and add to list
        missing = [alert for aid, alert in alerts.items() if alert["path"][0] == group and aid not in seen_ids]
        if missing:
            missing.sort(key=lambda a: a.get("timestamp", ""))
            group_leaves.extend(missing)
            pipe = redis_client.pipeline()
            for m in missing:
                pipe.rpush(order_key, m["id"])
            pipe.execute()

        result.extend(group_leaves)

    return result

@router.delete("/tree/{alert_id}")
def delete_tree_alert(alert_id: str):
    alert_json = redis_client.hget(tree_alerts_key, alert_id)
    if not alert_json:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert = json.loads(alert_json)
    group = alert["path"][0]
    redis_client.lrem(f"{group_leaves_prefix}{group}", 0, alert_id)
    redis_client.hdel(tree_alerts_key, alert_id)
    return {"message": "Tree alert deleted"}

class ReorderPayload(BaseModel):
    ordered_ids: list[str]

@router.post("/group/{group}/reorder")
def reorder_group(group: str, payload: ReorderPayload):
    ordered_ids = payload.ordered_ids
    # Validate (optional, for safety)
    pipe = redis_client.pipeline()
    pipe.delete(f"{group_leaves_prefix}{group}")
    for aid in ordered_ids:
        alert_json = redis_client.hget(tree_alerts_key, aid)
        if not alert_json:
            continue  # Skip invalid
        alert = json.loads(alert_json)
        if alert["path"][0] != group:
            continue  # Wrong group
        pipe.rpush(f"{group_leaves_prefix}{group}", aid)
    pipe.execute()
    return {"message": "Order updated"}

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

@router.post("/tree-lite")
def add_tree_leaf(data: dict):
    required_keys = {'symbol', 'qty', 'path'}
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
        "path": data["path"],
        "last_price": last_price,
        "timestamp": datetime.datetime.now().isoformat()
    }

    redis_client.hset(tree_alerts_key, alert_id, json.dumps(alert_data))
    group = alert_data["path"][0]
    redis_client.rpush(f"{group_leaves_prefix}{group}", alert_id)
    return {"id": alert_id}

class QtyUpdate(BaseModel):
    qty: int

@router.put("/tree/{alert_id}/qty")
def update_tree_qty(alert_id: str, payload: QtyUpdate):
    alert_json = redis_client.hget(tree_alerts_key, alert_id)
    if not alert_json:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert = json.loads(alert_json)
    alert["qty"] = payload.qty
    alert["timestamp"] = datetime.datetime.now().isoformat()
    redis_client.hset(tree_alerts_key, alert_id, json.dumps(alert))
    return {"message": "Qty updated", "qty": payload.qty}

# ---------- Group Alerts ----------


@router.get("/group-targets")
def get_group_targets():
    all_data = redis_client.hgetall(group_alerts_key)
    results = {}

    for group_name, value in all_data.items():
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
    if not redis_client.lpos(groups_order_key, group):
        redis_client.rpush(groups_order_key, group)
    redis_client.hset(group_alerts_key, group, target.json())
    return {"message": "Group target set", "group": group, "data": target}


@router.delete("/group-targets/{group}")
def delete_group_target(group: str):
    redis_client.hdel(group_alerts_key, group)
    redis_client.delete(f"{group_leaves_prefix}{group}")
    redis_client.lrem(groups_order_key, 0, group)
    return {"message": "Group target deleted", "group": group}

class ReorderGroupsPayload(BaseModel):
    ordered_groups: list[str]

@router.post("/groups/reorder")
def reorder_groups(payload: ReorderGroupsPayload):
    ordered_groups = payload.ordered_groups
    redis_client.delete(groups_order_key)
    for group in ordered_groups:
        redis_client.rpush(groups_order_key, group)
    return {"message": "Groups order updated"}
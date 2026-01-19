from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from urllib.parse import unquote
from common.config import get_redis_client
import datetime, uuid, json, re
from common.trading_hours import TradingHours
from common.my_logger import logger
from pathlib import Path
from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel

class GroupTarget(BaseModel):
    operator: Optional[Literal["<", "=", ">", "Range"]] = None
    target: Optional[str] = None
    status: Literal["Pending", "Active", "Triggered", "Acknowledged"]

router = APIRouter(prefix="/alerts2", tags=["alerts-api"])
redis_client = get_redis_client()
alerts_json_key = "alerts_json"
trading_hour = TradingHours(start_buffer=60)
BASE_DIR = Path(__file__).resolve().parent

OPERATORS = {
    '<': lambda a, b: a < b,
    '=': lambda a, b: a == b,
    '>': lambda a, b: a > b
}

def get_redis_key():
    return f"tick:{(datetime.date.today()-datetime.timedelta(days=0)).strftime('%Y%m%d')}"

def load_alerts_data():
    data = redis_client.json().get(alerts_json_key)
    return data if data is not None else {"groups_order": [], "groups": {}}

def save_alerts_data(data):
    redis_client.json().set(alerts_json_key, ".", data)

@router.get("/test")
def read_root():
    return {"message": "Hello, Alerts Spread!"}

@router.get("/play-alert")
def play_alert():
    return FileResponse(BASE_DIR / "alert.mp3", media_type='audio/mp3')

@router.get("/symbols")
def get_symbols() -> Dict[str, Any]:
    redis_key = get_redis_key()
    # All keys & values will already be decoded (decode_responses=True)
    raw_map = redis_client.hgetall(redis_key)

    exchanges: Dict[str, Any] = {}

    for field, value_str in raw_map.items():
        try:
            value = json.loads(value_str) if value_str else {}
            tradable = bool(value.get("tradable", False))
        except Exception as e:
            logger.warning(f"Skipping field {field!r} due to JSON error: {e}")
            tradable = False

        if ":" not in field:
            continue

        exchange, sym = field.split(":", 1)

        # NSE/BSE logic — if tradable, classify under 'EQ'
        if exchange in ("NSE", "BSE"):
            key = f"EQ:{exchange}" if tradable else exchange
            exchanges.setdefault(key, {}).setdefault("symbols", []).append(sym)
            continue

        # Other exchanges (options, futures, etc.)
        try:
            match = re.match(r"^([A-Z]+)(\d.{4})(.*)(..)$", sym)
            if not match:
                exchanges.setdefault(exchange, {}).setdefault("symbols_unparsed", []).append(sym)
                continue

            symbol_part, exp_str, strike, opt_type = match.groups()
            exchanges.setdefault(exchange, {}) \
                     .setdefault(symbol_part, {}) \
                     .setdefault(exp_str, {}) \
                     .setdefault(strike, []) \
                     .append(opt_type)
        except Exception as e:
            logger.warning(f"Error parsing {sym}: {e}")
            exchanges.setdefault(exchange, {}).setdefault("symbols_unparsed", []).append(sym)

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

    alerts_data = load_alerts_data()
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
        "target": data["target"],
        "status": "Active",
        "path": data["path"],
        "last_price": last_price,
        "timestamp": datetime.datetime.now().isoformat()
    }

    group = data["path"][0]
    if group not in alerts_data["groups"]:
        alerts_data["groups"][group] = {"target": {"operator": "", "target": None, "status": "Pending"}, "leaves_order": [], "leaves": {}}
        if group not in alerts_data["groups_order"]:
            alerts_data["groups_order"].append(group)
    alerts_data["groups"][group]["leaves"][alert_id] = alert_data
    alerts_data["groups"][group]["leaves_order"].append(alert_id)
    save_alerts_data(alerts_data)
    return {"id": alert_id}

@router.get("/tree")
def get_tree_alerts():
    alerts_data = load_alerts_data()
    ordered_groups = alerts_data.get("groups_order", [])
    all_groups_set = set(alerts_data["groups"].keys())
    missing_groups = sorted(all_groups_set - set(ordered_groups))
    changed = False
    if missing_groups:
        ordered_groups.extend(missing_groups)
        alerts_data["groups_order"] = ordered_groups
        changed = True

    result = []
    redis_key = get_redis_key()
    now_iso = datetime.datetime.now().isoformat()

    for group in ordered_groups:
        if group not in alerts_data["groups"]:
            continue
        group_data = alerts_data["groups"][group]
        target_data = group_data.get("target", {"operator": "", "target": None, "status": "Pending"})
        group_row = {
            "id": f"group-{group}",
            "groupName": group,
            "symbol": group,  # ADDED: Set symbol to group name for autoGroupColumnDef display
            "operator": target_data.get("operator", ""),
            "target": target_data.get("target"),
            "status": target_data.get("status", "Pending"),
            "path": [group],  # For treeData structure
            # Note: last_price for group is calculated in frontend valueGetter
            # timestamp for group will be max from leaves in frontend
        }
        result.append(group_row)

        # Build leaves with current prices/timestamps
        for leaf_id in group_data.get("leaves_order", []):
            if leaf_id not in group_data["leaves"]:
                continue
            leaf_data = group_data["leaves"][leaf_id].copy()  # Avoid modifying original
            symbol = leaf_data["symbol"]

            # Fetch current tick data
            tick_str = redis_client.hget(redis_key, symbol)
            if tick_str:
                try:
                    tick = json.loads(tick_str)
                    leaf_data["last_price"] = tick.get("last_price", leaf_data.get("last_price", 0))
                    # Repurpose 'timestamp' for display as current price time (matches WS behavior)
                    leaf_data["timestamp"] = tick.get("exchange_timestamp", leaf_data["timestamp"])
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Error updating tick for {symbol}: {e}")
                    # Fallback: use now if no exchange_timestamp
                    leaf_data["timestamp"] = tick.get("exchange_timestamp", now_iso)
            else:
                # No tick data: use now for timestamp fallback
                leaf_data["timestamp"] = now_iso

            # Ensure path is set for treeData
            leaf_data["path"] = [group, symbol]
            result.append(leaf_data)

    if changed:
        save_alerts_data(alerts_data)
    return result

@router.delete("/tree/{alert_id}")
def delete_tree_alert(alert_id: str):
    alerts_data = load_alerts_data()
    found = False
    for group, group_data in alerts_data["groups"].items():
        if alert_id in group_data["leaves"]:
            del group_data["leaves"][alert_id]
            group_data["leaves_order"] = [aid for aid in group_data["leaves_order"] if aid != alert_id]
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Alert not found")
    save_alerts_data(alerts_data)
    return {"message": "Tree alert deleted"}

class ReorderPayload(BaseModel):
    ordered_ids: list[str]

@router.post("/group/{group}/reorder")
def reorder_group(group: str, payload: ReorderPayload):
    alerts_data = load_alerts_data()
    if group not in alerts_data["groups"]:
        raise HTTPException(status_code=404, detail="Group not found")
    group_data = alerts_data["groups"][group]
    ordered_ids = []
    for aid in payload.ordered_ids:
        if aid in group_data["leaves"] and group_data["leaves"][aid]["path"][0] == group:
            ordered_ids.append(aid)
    group_data["leaves_order"] = ordered_ids
    save_alerts_data(alerts_data)
    return {"message": "Order updated"}

@router.post("/tree/{alert_id}/ack")
def acknowledge_tree_alert(alert_id: str):
    alerts_data = load_alerts_data()
    found = False
    for group_data in alerts_data["groups"].values():
        if alert_id in group_data["leaves"]:
            group_data["leaves"][alert_id]["status"] = "Acknowledged"
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Alert not found")
    save_alerts_data(alerts_data)
    return {"message": "Alert acknowledged"}

@router.post("/tree/{alert_id}/reset")
def reset_tree_alert(alert_id: str):
    alerts_data = load_alerts_data()
    found = False
    for group_data in alerts_data["groups"].values():
        if alert_id in group_data["leaves"]:
            alert = group_data["leaves"][alert_id]
            if alert.get('status') != 'Acknowledged':
                raise HTTPException(status_code=400, detail="Only acknowledged alerts can be reset")
            alert["status"] = "Active"
            alert["timestamp"] = datetime.datetime.now().isoformat()
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Alert not found")
    save_alerts_data(alerts_data)
    return {"message": "Alert reset to Active"}

@router.post("/tree-lite")
def add_tree_leaf(data: dict):
    required_keys = {'symbol', 'qty', 'path'}
    if not required_keys.issubset(data.keys()):
        raise HTTPException(status_code=400, detail="Missing required fields")

    alerts_data = load_alerts_data()
    alert_id = str(uuid.uuid4())
    raw_symbol = data['symbol'].upper().strip()

    # If UI sends something like "EQ:NSE:RELIANCE" convert to "NSE:RELIANCE"
    redis_field = raw_symbol
    try:
        parts = raw_symbol.split(":")
        if parts[0] == "EQ" and len(parts) >= 3:
            # EQ:{Exchange}:{SYMBOL...} -> {Exchange}:{SYMBOL...}
            exchange = parts[1]
            sym = ":".join(parts[2:])
            redis_field = f"{exchange}:{sym}"
    except Exception:
        # keep raw_symbol if anything unexpected happens
        redis_field = raw_symbol

    qty = data.get("qty", 1)

    # Try to fetch tick data; fallback to raw_symbol if redis_field not found
    tick_data = redis_client.hget(get_redis_key(), redis_field)
    if not tick_data and redis_field != raw_symbol:
        # try fallback (in case UI used a different format)
        tick_data = redis_client.hget(get_redis_key(), raw_symbol)

    if not tick_data:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {raw_symbol}")

    last_price = json.loads(tick_data).get("last_price", 0)

    alert_data = {
        "id": alert_id,
        "symbol": raw_symbol,
        "qty": qty,
        "path": data["path"],
        "last_price": last_price,
        "timestamp": datetime.datetime.now().isoformat(),
        "operator": "", # ADDED: Default for leaf
        "target": None,
        "status": "Pending"
    }

    group = data["path"][0]
    is_new_group = group not in alerts_data["groups"]
    if is_new_group:
        alerts_data["groups"][group] = {"target": {"operator": "", "target": None, "status": "Pending"}, "leaves_order": [], "leaves": {}}
        if group not in alerts_data["groups_order"]:
            alerts_data["groups_order"].append(group)
    alerts_data["groups"][group]["leaves"][alert_id] = alert_data
    alerts_data["groups"][group]["leaves_order"].append(alert_id)
    if is_new_group:
        current_total = qty * last_price
        target_value = current_total + 1 if current_total > 0 else 1
        alerts_data["groups"][group]["target"] = {"operator": "=", "target": str(target_value), "status": "Active"}
    save_alerts_data(alerts_data)
    return {"id": alert_id}

class QtyUpdate(BaseModel):
    qty: float

@router.put("/tree/{alert_id}/qty")
def update_tree_qty(alert_id: str, payload: QtyUpdate):
    alerts_data = load_alerts_data()
    found = False
    for group_data in alerts_data["groups"].values():
        if alert_id in group_data["leaves"]:
            group_data["leaves"][alert_id]["qty"] = payload.qty
            group_data["leaves"][alert_id]["timestamp"] = datetime.datetime.now().isoformat()
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Alert not found")
    save_alerts_data(alerts_data)
    return {"message": "Qty updated", "qty": payload.qty}

# ADDED: Endpoint for leaf target
@router.post("/tree/{alert_id}/target")
def set_leaf_target(alert_id: str, target: GroupTarget):
    alerts_data = load_alerts_data()
    found = False
    for group_data in alerts_data["groups"].values():
        if alert_id in group_data["leaves"]:
            group_data["leaves"][alert_id]["operator"] = target.operator
            group_data["leaves"][alert_id]["target"] = target.target
            group_data["leaves"][alert_id]["status"] = target.status
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Leaf not found")
    save_alerts_data(alerts_data)
    return {"message": "Leaf target set"}

# ---------- Group Alerts ----------

@router.get("/group-targets")
def get_group_targets():
    alerts_data = load_alerts_data()
    results = {group: group_data["target"] for group, group_data in alerts_data["groups"].items()}
    return results


@router.get("/group-targets/{group}")
def get_group_target(group: str):
    alerts_data = load_alerts_data()
    if group not in alerts_data["groups"]:
        return JSONResponse(status_code=404, content={"message": "Group target not found"})
    return alerts_data["groups"][group]["target"]


@router.post("/group-targets/{group}")
def set_group_target(group: str, target: GroupTarget):
    alerts_data = load_alerts_data()
    if group not in alerts_data["groups"]:
        alerts_data["groups"][group] = {"target": {"operator": "", "target": None, "status": "Pending"}, "leaves_order": [], "leaves": {}}
        if group not in alerts_data["groups_order"]:
            alerts_data["groups_order"].append(group)
    alerts_data["groups"][group]["target"] = target.dict()
    save_alerts_data(alerts_data)
    return {"message": "Group target set", "group": group, "data": target}


@router.delete("/group-targets/{group}")
def delete_group_target(group: str):
    alerts_data = load_alerts_data()
    if group in alerts_data["groups"]:
        del alerts_data["groups"][group]
        alerts_data["groups_order"] = [g for g in alerts_data["groups_order"] if g != group]
        save_alerts_data(alerts_data)
    return {"message": "Group target deleted", "group": group}

class ReorderGroupsPayload(BaseModel):
    ordered_groups: list[str]

@router.post("/groups/reorder")
def reorder_groups(payload: ReorderGroupsPayload):
    alerts_data = load_alerts_data()
    ordered_groups = [g for g in payload.ordered_groups if g in alerts_data["groups"]]
    alerts_data["groups_order"] = ordered_groups
    save_alerts_data(alerts_data)
    return {"message": "Groups order updated"}
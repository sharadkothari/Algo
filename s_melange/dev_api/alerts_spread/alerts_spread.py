from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from urllib.parse import unquote
from common.config import get_redis_client
import datetime, uuid, json, re
from common.trading_hours import TradingHours
from common.my_logger import logger
from pathlib import Path
from typing import Optional, Literal
from pydantic import BaseModel

class GroupTarget(BaseModel):
    operator: Optional[Literal["<", "=", ">", "Range"]] = None
    target: Optional[str] = None  # CHANGED: From float to str
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
        "target": data["target"],  # CHANGED: Keep as provided (str or float, but will be str)
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
    for group in ordered_groups:
        if group not in alerts_data["groups"]:
            continue
        group_data = alerts_data["groups"][group]
        target_data = group_data.get("target", {"operator": "", "target": None, "status": "Pending"})
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

        leaves_order = group_data.get("leaves_order", [])
        leaves = group_data.get("leaves", {})
        group_leaves = []
        seen_ids = set()
        for aid in leaves_order:
            if aid in leaves and aid not in seen_ids:
                leaf = leaves[aid].copy()
                leaf["id"] = aid  # Ensure ID is set
                group_leaves.append(leaf)
                seen_ids.add(aid)

        # Append any unsorted/missing leaves (fallback), sort by timestamp, and add to list
        missing = [leaves[aid].copy() for aid in leaves if aid not in seen_ids and leaves[aid]["path"][0] == group]
        if missing:
            missing.sort(key=lambda a: a.get("timestamp", ""))
            group_leaves.extend(missing)
            group_data["leaves_order"] = [leaf["id"] for leaf in group_leaves]
            changed = True

        result.extend(group_leaves)

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
        alerts_data["groups"][group]["target"] = {"operator": "=", "target": str(target_value), "status": "Active"}  # CHANGED: target as str
    save_alerts_data(alerts_data)
    return {"id": alert_id}

class QtyUpdate(BaseModel):
    qty: int

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
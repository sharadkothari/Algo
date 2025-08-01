from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from common.config import get_redis_client
from pathlib import Path
import uuid
import json
import threading
import time
import datetime
from urllib.parse import unquote
import re
import redis

router = APIRouter(prefix="/alerts", tags=["alerts"])
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR))

redis_client: redis = get_redis_client()
alerts_key = "alerts"  # Store alerts in Redis


def get_redis_key():
    return f"tick:{datetime.date.today().strftime('%Y%m%d')}"


@router.get('/', response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("alerts.html", {"request": request})


@router.get('/play-alert')
def play_alert():
    return FileResponse(BASE_DIR / "alert.mp3", media_type='audio/mp3')


@router.get('/symbols')
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

                if symbol_part not in exchanges[exchange]:
                    exchanges[exchange][symbol_part] = {}

                if exp_str not in exchanges[exchange][symbol_part]:
                    exchanges[exchange][symbol_part][exp_str] = {}

                exchanges[exchange][symbol_part][exp_str].setdefault(strike, []).append(opt_type)
            except Exception as e:
                print(f"Error parsing {sym}: {e}")

    return exchanges


@router.get('/tick-data/{symbol}')
def get_tick_data(symbol):
    symbol = unquote(symbol)
    data = redis_client.hget(get_redis_key(), symbol)
    if data:
        return json.loads(data)
    raise HTTPException(status_code=404, detail="Symbol not found")


@router.post('/alerts')
def add_alert(data: dict):
    required_keys = {'symbol', 'operator', 'target'}
    if not required_keys.issubset(data.keys()):
        raise HTTPException(status_code=400, detail="Missing required fields")

    symbol = data['symbol']
    tick_data = redis_client.hget(get_redis_key(), symbol)
    start_price = json.loads(tick_data).get('last_price') if tick_data else None

    alert_id = str(uuid.uuid4())
    alert_data = {
        'symbol': symbol,
        'operator': data['operator'],
        'target': float(data['target']),
        'status': "Active",
        "timestamp": datetime.datetime.now().isoformat(),
        'start_price': start_price,
    }
    redis_client.hset(alerts_key, alert_id, json.dumps(alert_data))
    return {"id": alert_id, "message": "Alert added"}


@router.get('/alerts')
def get_alerts():
    alerts_data = redis_client.hgetall(alerts_key)
    return {k: json.loads(v) for k, v in alerts_data.items()}


@router.delete('/alerts/{alert_id}')
def delete_alert(alert_id: str):
    if redis_client.hdel(alerts_key, alert_id):
        return {"message": "Alert deleted"}
    raise HTTPException(status_code=404, detail="Alert not found")


@router.post('/alerts/{alert_id}/ack')
def acknowledge_alert(alert_id: str):
    alert_json = redis_client.hget(alerts_key, alert_id)
    if not alert_json:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert = json.loads(alert_json)
    alert["status"] = "Acknowledged"
    redis_client.hset(alerts_key, alert_id, json.dumps(alert))
    return {"message": "Alert acknowledged"}


@router.post('/alerts/{alert_id}/reset')
def reset_alert(alert_id: str):
    alert_json = redis_client.hget(alerts_key, alert_id)
    if not alert_json:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert = json.loads(alert_json)
    if alert['status'] != 'Acknowledged':
        raise HTTPException(status_code=400, detail="Only acknowledged alerts can be reset")
    alert["status"] = "Active"
    alert["timestamp"] = datetime.datetime.now().isoformat()
    redis_client.hset(alerts_key, alert_id, json.dumps(alert))
    return {"message": "Alert reset to Active"}


OPERATORS = {
    '<': lambda a, b: a < b,
    '=': lambda a, b: a == b,
    '>': lambda a, b: a > b
}


def monitor_alerts():
    while True:
        alerts_data = redis_client.hgetall(alerts_key)
        for alert_id, alert_json in alerts_data.items():
            alert = json.loads(alert_json)
            if alert['status'] in ('Triggered', "Acknowledged"):  # Skip already triggered alerts
                continue

            symbol = alert['symbol']
            tick_data = redis_client.hget(get_redis_key(), symbol)

            if tick_data:
                tick_data = json.loads(tick_data)
                last_price = tick_data.get('last_price')
                operator = alert['operator']

                if operator in OPERATORS and OPERATORS[operator](last_price, alert['target']):
                    alert['status'] = 'Triggered'
                    redis_client.hset(alerts_key, alert_id, json.dumps(alert))
        time.sleep(2)


threading.Thread(target=monitor_alerts, daemon=True).start()


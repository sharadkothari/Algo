from flask import Flask, render_template, jsonify, request, send_from_directory
from common.config import redis_host, redis_port, redis_db
from common.utils import list_routes, register_service
from pathlib import Path
import uuid
import json
import threading
import time
import datetime
import redis
from urllib.parse import unquote
import re
import os

app = Flask(__name__, template_folder=".", static_folder=".")
app.config['TEMPLATES_AUTO_RELOAD'] = True
module_name = Path(__file__).stem
port = 5006

redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
alerts_key = "alerts"  # Store alerts in Redis


def get_redis_key():
    return f'tick:{datetime.date.today().strftime('%Y%m%d')}'


@app.route('/')
def index():
    return render_template('alerts.html')

@app.route('/play-alert')
def play_alert():
    return send_from_directory(".",'alert.mp3', mimetype='audio/mp3')


@app.route('/symbols', methods=['GET'])
def get_symbols():
    symbols = redis_client.hkeys(get_redis_key())
    exchanges = {}

    for symbol in symbols:
        if ":" in symbol:
            exchange, sym = symbol.split(":", 1)

            if exchange not in exchanges:
                exchanges[exchange] = {}

            # Handling index and stock symbols
            if exchange in ("NSE", "BSE"):
                exchanges[exchange].setdefault("symbols", []).append(sym)
                continue

            # Handling options format
            try:
                match = re.match(r"^([A-Z]+)(\d.{4})(.*)(..)$", sym)
                symbol_part = match.group(1)  # String till first digit
                exp_str = match.group(2)  # First digit + next 4 characters
                strike = match.group(3)  # Balance characters excluding last two
                opt_type = match.group(4)  # Last two characters

                if symbol_part not in exchanges[exchange]:
                    exchanges[exchange][symbol_part] = {}

                if exp_str not in exchanges[exchange][symbol_part]:
                    exchanges[exchange][symbol_part][exp_str] = {}

                exchanges[exchange][symbol_part][exp_str].setdefault(strike, []).append(opt_type)
            except Exception as e:
                print(f"Error parsing {sym}: {e}")

    return jsonify(exchanges)


@app.route('/tick-data/<symbol>', methods=['GET'])
def get_tick_data(symbol):
    symbol = unquote(symbol)
    data = redis_client.hget(get_redis_key(), symbol)
    if data:
        return jsonify(json.loads(data))
    return jsonify({'error': 'Symbol not found'}), 404


@app.route('/alerts', methods=['POST'])
def add_alert():
    data = request.get_json() or {}
    if 'symbol' not in data or 'operator' not in data or 'target' not in data:
        return jsonify({'error': 'Missing required fields'}), 400

    symbol = data['symbol']

    # Fetch latest tick data from Redis
    tick_data = redis_client.hget(get_redis_key(), symbol)
    if tick_data:
        tick_data = json.loads(tick_data)
        start_price = tick_data.get('last_price', None)  # Get last traded price
    else:
        start_price = None

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
    return jsonify({'id': alert_id, 'message': 'Alert added'})


@app.route('/alerts', methods=['GET'])
def get_alerts():
    alerts_data = redis_client.hgetall(alerts_key)
    alerts = {alert_id: json.loads(alert_json) for alert_id, alert_json in alerts_data.items()}
    return jsonify(alerts)


@app.route('/alerts/<alert_id>', methods=['DELETE'])
def delete_alert(alert_id):
    if redis_client.hdel(alerts_key, alert_id):
        return jsonify({'message': 'Alert deleted'})
    return jsonify({'error': 'Alert not found'}), 404


@app.route('/alerts/<alert_id>/ack', methods=['POST'])
def acknowledge_alert(alert_id):
    alert_json = redis_client.hget(alerts_key, alert_id)
    if not alert_json:
        return jsonify({'error': 'Alert not found'}), 404

    alert = json.loads(alert_json)
    alert['status'] = 'Acknowledged'
    redis_client.hset(alerts_key, alert_id, json.dumps(alert))
    return jsonify({'message': 'Alert acknowledged'})


OPERATORS = {
    '<': lambda a, b: a < b,
    '=': lambda a, b: a == b,
    '>': lambda a, b: a > b
}


@app.route("/routes", methods=["GET"])
def get_routes():
    return list_routes(app)


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200


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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port, debug=True)

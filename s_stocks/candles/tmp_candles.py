from flask import Flask, jsonify, json, render_template
from common.config import server_url
from common.utils import list_routes, register_service
from pathlib import Path
from candles import Candles

app = Flask(__name__, template_folder=".", static_folder=".")
app.config['TEMPLATES_AUTO_RELOAD'] = True
module_name = Path(__file__).stem
port = 5022
candles = Candles()


@app.route("/hello")
def hello():
    print('hello from candles', flush=True)
    return "Hello, Candles!"


@app.route('/open')
def open():
    return json.dumps(candles.in_progress_candles, default=lambda x: x.isoformat())


@app.route('/closed')
def closed():
    return json.dumps(candles.completed_candles, default=lambda x: x.isoformat())


@app.route("/routes", methods=["GET"])
def get_routes():
    return list_routes(app)


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port, debug=True)

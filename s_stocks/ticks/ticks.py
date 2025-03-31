from flask import Flask, jsonify, json, render_template
from common.utils import list_routes, register_service
from pathlib import Path
from kite_socket import KiteSocket

app = Flask(__name__, template_folder=".", static_folder=".")
app.config['TEMPLATES_AUTO_RELOAD'] = True
module_name = Path(__file__).stem
port = 5021
kws = KiteSocket(client_id="YM3006")


@app.route("/hello")
def hello():
    return "Hello, World!"


@app.route("/status")
def status():
    cur_status = {"kws connected": kws.kws.is_connected()}
    return jsonify(cur_status)


@app.route('/ticks')
def ticks():
    return json.dumps(kws.ticks, default=lambda x: x.isoformat())


@app.route("/routes", methods=["GET"])
def get_routes():
    return list_routes(app)


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port, debug=True)

from flask import Flask, jsonify, render_template
from common.utils import list_routes, register_service
from pathlib import Path
import requests
from common.my_logger import redis_handler
import redis

app = Flask(__name__, template_folder=".", static_folder=".")
app.config['TEMPLATES_AUTO_RELOAD'] = True
module_name = Path(__file__).stem
port = 5003


def get_status(status):
    return {"status": "ok" if status else "down"}


def check_server_path(server, path):
    try:
        return requests.get(f"http://{server}/{path}", timeout=2).json()
    except:
        return jsonify({"status": "down"})


def check_redis():
    try:
        return redis_handler.redis_client.ping()  # True if Redis is reachable
    except redis.ConnectionError:
        return False


@app.route('/dashboard')
def health_dashboard():
    return render_template('health_db.html')


@app.route("/redis")
def redis_health():
    return jsonify(get_status(check_redis()))


@app.route("/flask")
def flask_health():
    return jsonify(get_status(True))


@app.route("/u530/health")
def u530_health():
    return check_server_path("u530", "health")


@app.route("/u530/kws_status")
def u530_kws():
    return check_server_path("u530", "kws_status")


@app.route("/e6330/health")
def e6330_health():
    return check_server_path("e6330", "health")


@app.route("/e6330/kws_status")
def e6330_kws_status():
    return check_server_path("e6330", "kws_status")


@app.route("/e6330-2/health")
def e6330_2_health():
    return check_server_path("e6330-2", "health")


@app.route("/e6330-2/kws_status")
def e6330_2_kws():
    return check_server_path("e6330-2", "kws_status")


@app.route("/routes", methods=["GET"])
def get_routes():
    return list_routes(app)



@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port, debug=True)

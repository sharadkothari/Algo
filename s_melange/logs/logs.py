from flask import Flask, render_template, jsonify, request
from common.config import redis_host, redis_port, redis_db
from common.utils import list_routes, register_service
from pathlib import Path
import redis

app = Flask(__name__, template_folder=".", static_folder=".")
app.config['TEMPLATES_AUTO_RELOAD'] = True
module_name = Path(__file__).stem
port = 5005
redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)


@app.route("/streams")
def get_streams():
    """Fetch all Redis stream keys."""
    try:
        streams = [key for key in redis_client.scan_iter("*") if redis_client.type(key) == "stream"]
        return jsonify(streams)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/get")
def get_logs():
    stream_name = request.args.get('stream', 'default_stream')
    last_id = request.args.get("since", "0")  # Default to fetching all logs
    if not stream_name:
        return jsonify({"error": "Stream parameter missing"}), 400

    logs = redis_client.xrevrange(stream_name, count=100)  # Fetch last 100 logs
    logs = [
        {
            "timestamp": log[0].split("-")[0],  # Extract timestamp from Redis Stream ID
            "level": log[1].get("level", "INFO"),  # Default to INFO if missing
            "module": log[1].get("module", ""),
            "message": log[1]["message"]
        }
        for log in reversed(logs)
    ]
    return jsonify(logs)


@app.route("/view")
def view_logs():
    return render_template("logviewer.html")


@app.route("/routes", methods=["GET"])
def get_routes():
    return list_routes(app)

@app.route("/register")
def register():
    return register_service(module_name=module_name, port=port)


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200


register()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port, debug=True)

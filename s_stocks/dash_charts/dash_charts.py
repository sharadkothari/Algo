from flask import Flask, jsonify
from dashapp import DashApp
from common.utils import list_routes
from pathlib import Path
import os

app = Flask(__name__, template_folder=".", static_folder=".")
app.config['TEMPLATES_AUTO_RELOAD'] = True

module_name = Path(__file__).stem
port = 5025

dash_path_pre = base_path = f"/{module_name}" if os.getenv("DOCKERIZED") else ""

for dash_app in ['dash1', "dash2"]:
    DashApp(app_name=dash_app,server=app, url_base_pathname=f"/{dash_app}/",debug=True)

@app.route('/')
def hello():
    return "Hello from dash_charts"


@app.route("/routes", methods=["GET"])
def get_routes():
    return list_routes(app)


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port, debug=True)
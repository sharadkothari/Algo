from flask import Flask, jsonify, json, send_file, redirect, render_template
from common.utils import list_routes, register_service
from pathlib import Path
from dynamic_candles_builder import DynamicCandlesBuilder
import os
import logging

app = Flask(__name__, template_folder=".", static_folder=".")
app.config['TEMPLATES_AUTO_RELOAD'] = True


module_name = Path(__file__).stem
port = 5023
dynamic_candles = DynamicCandlesBuilder()


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
# atexit.register(dynamic_candles.graceful_exit)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port, debug=True)
from flask import Flask, render_template, jsonify
from common.utils import list_routes, register_service
from pathlib import Path

app = Flask(__name__, template_folder=".", static_folder=".")
app.config['TEMPLATES_AUTO_RELOAD'] = True
module_name = Path(__file__).stem
port = 5004

@app.route('/')
def dbone():
    return render_template('dbone.html')


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

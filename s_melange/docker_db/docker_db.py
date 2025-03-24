from flask import Flask, render_template, jsonify
from common.utils import list_routes
from pathlib import Path
from docker_handler import DockerHandler

app = Flask(__name__, template_folder=".", static_folder=".")
app.config['TEMPLATES_AUTO_RELOAD'] = True
module_name = Path(__file__).stem
port = 5008
dh = DockerHandler()


@app.route("/routes", methods=["GET"])
def get_routes():
    return list_routes(app)


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200


@app.route("/")
def docker_db():
    return render_template("docker_db.html")

@app.route('/services')
def get_services():
    return jsonify(dh.get_services())


@app.route('/start/<container_id>', methods=['POST'])
def start_container(container_id):
    result = dh.start_container(container_id)
    return jsonify(result[0]), result[1]


@app.route('/stop/<container_id>', methods=['POST'])
def stop_container(container_id):
    result = dh.stop_container(container_id)
    return jsonify(result[0]), result[1]

@app.route('/restart/<container_id>', methods=['POST'])
def restart_container(container_id):
    result = dh.restart_container(container_id)
    return jsonify(result[0]), result[1]

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port, debug=True)

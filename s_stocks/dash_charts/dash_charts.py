from flask import Flask
from dashapp import DashApp
from common.utils import list_routes, register_service
from pathlib import Path

app = Flask(__name__, template_folder=".", static_folder=".")
app.config['TEMPLATES_AUTO_RELOAD'] = True

module_name = Path(__file__).stem
port = 5025

dash1 = DashApp(app_name="dash1", server=app, url_base_pathname="/dash1/", debug=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port, debug=True)
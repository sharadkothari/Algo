from flask import Flask, render_template, jsonify
from common.config import redis_host, redis_port, redis_db
from common.utils import list_routes
import requests
import redis
from common.my_logger import logger
from common.telegram_bot import TelegramBotMain, TelegramBotService
import threading

app = Flask(__name__, template_folder=".", static_folder=".")
app.config['TEMPLATES_AUTO_RELOAD'] = True
redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
pubsub = redis_client.pubsub()
bot_main = TelegramBotMain()

@app.route("/check")
def check():
    url = "http://nginx/streams/health"
    print(url, flush=True)
    response = requests.get(url).json()
    print(response, flush=True)
    return jsonify(response)


@app.route("/routes", methods=["GET"])
def get_routes():
    return list_routes(app)


@app.route("/")
def home():
    services_data = []
    registered_services = redis_client.hgetall("services")
    for name, container_port in registered_services.items():
        if name != "home":
            url = f"http://nginx/{name}/routes"
        else:
            url = "http://nginx/routes"
        port = container_port.split(':')[-1]
        try:
            response = requests.get(f"http://nginx/{name}/routes", timeout=2)
            if response.status_code == 200:
                routes = response.json()
                services_data.append({"name": name, "port": port, "routes": routes})
        except requests.exceptions.RequestException:
            services_data.append({"name": name, "port": port, "routes": "Service Unreachable"})

    return render_template("home.html", services=services_data)


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)

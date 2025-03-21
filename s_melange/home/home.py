from flask import Flask, render_template, jsonify
from common.config import redis_host, redis_port, redis_db
import requests
import redis
import datetime
from common.my_logger import logger
import threading
import asyncio
import httpx
from common.telegram_bot import TelegramBotMain, TelegramBotService

app = Flask(__name__, template_folder=".", static_folder=".")
app.config['TEMPLATES_AUTO_RELOAD'] = True
redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)

registered_services = {}
tbot_main = TelegramBotMain()
tbot_service = TelegramBotService()


@app.route("/services")
def get_services():
    return jsonify(registered_services)

@app.route("/check")
def check():
    url = "http://nginx/streams/health"
    print(url, flush=True)
    response = requests.get(url).json()
    print(response, flush=True)
    return jsonify(response)

@app.route("/")
def home():
    services_data = []

    for name, port in registered_services.items():
        try:
            response = requests.get(f"http://nginx/{name}/routes", timeout=2)
            if response.status_code == 200:
                routes = response.json()
                services_data.append({"name": name, "port": port, "routes": routes})
        except requests.exceptions.RequestException:
            services_data.append({"name": name, "port": port, "routes": "Service Unreachable"})

    return render_template("home.html", services=services_data)


async def check_service(name):
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(f"http://nginx/{name}/health")
            return name, response.status_code == 200
    except httpx.RequestError:
        return name, False


async def health_check():
    global registered_services
    while True:
        try:
            services = redis_client.hgetall("services")
            tasks = [check_service(name) for name, _ in services.items()]
            results = await asyncio.gather(*tasks)

            for name, is_up in results:
                redis_store(service_name=name, up=is_up)

            registered_services = services.copy()
        except Exception as e:
            logger.info(f"Health check error: {e}")
        await asyncio.sleep(10)

def redis_store(service_name, up=True):
    status_value = "up" if up else "dn"
    date_key = f'last_{status_value}'
    hash_name = f"service_status:{service_name}"
    last_status = redis_client.hget(hash_name, "status")

    # Debounce Status Change (Avoid Flapping Alerts)
    if not up:
        failure_count = redis_client.hincrby(hash_name, "failure_count", 1)
        if failure_count < 2:  # Require 2 failures before marking down
            return
    else:
        # pycharm expects value to be str
        # noinspection PyTypeChecker
        redis_client.hset(hash_name, "failure_count", 0)  #

    if last_status != status_value:
        pipe = redis_client.pipeline()
        pipe.hset(hash_name, "status", status_value)
        pipe.hset(hash_name, date_key, datetime.datetime.now().isoformat())
        pipe.execute()

        status_emoji = "🟢" if up else "🔴"
        message = f"{status_emoji} {service_name} : {status_value.upper()}"
        logger.info(message)
        tbot_service.send(message, chat_id=-1002340369818)


threading.Thread(target=lambda: asyncio.run(health_check()), daemon=True).start()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)

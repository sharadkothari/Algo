from flask import Flask, jsonify, request, json, Response
from common.config import get_redis_client
from common.utils import list_routes, register_service
from common.config import data_dir
from pathlib import Path
import requests
from common.my_logger import logger
import redis
from telegram_handler import TelegramHandlerManager
import datetime

app = Flask(__name__, template_folder=".", static_folder=".")
app.config['TEMPLATES_AUTO_RELOAD'] = True
module_name = Path(__file__).stem
port = 5007

with open(data_dir / 'telegram.json', 'r') as f:
    telegram_data = json.loads(f.read())

redis_client = get_redis_client()
TOKEN = telegram_data['token']
NGROK_URL = telegram_data['ngrok_url']
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TOKEN}"
ALLOWED_IPS = ["127.0.0.1", "::1", "100.123.122.115", "172.20.0.1", "100.103.219.96", "192.168.65.1"]
handler_manager = TelegramHandlerManager(api_url=TELEGRAM_API_URL, redis_client=redis_client)


@app.route("/set")
def set_webhook():
    webhook_url = f"{TELEGRAM_API_URL}/setWebhook"
    payload = {
        "url": f"{NGROK_URL}/webhook",
        "allowed_updates": ["message", "channel_post", "callback_query"]
    }
    response = requests.post(webhook_url, json=payload).json()
    logger.info(f"Webhook Setup Response: {response}")


@app.route("/status", methods=["GET"])
def webhook_status():
    """Fetch and return Telegram webhook status"""
    response = requests.get(f"{TELEGRAM_API_URL}/getWebhookInfo").json()
    return jsonify(response)


def send_message(chat_id, text, **kwargs):
    payload = {"chat_id": chat_id, "text": text, **kwargs}
    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload)
    return ""


@app.route("/send", methods=["POST"])
def send():
    data = request.get_json() or {}
    send_message(**data)
    return jsonify({"ok": True})


@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data received"}), 400
    else:
        redis_client.xadd("telegram_dump",
                          {"time": datetime.datetime.now().isoformat(timespec="seconds"),
                           "data": json.dumps(data)}, maxlen=1000)
        handler_manager.store_message(data)
    return jsonify({"status": "ok"})


def get_chat_id(chat_id, message):
    return f'chat_id:{chat_id}'


@app.route("/ngrok_url", methods=['GET'])
def ngrok_url():
    return NGROK_URL


@app.route("/routes", methods=["GET"])
def get_routes():
    if request.remote_addr not in ALLOWED_IPS:
        return jsonify({"error": f"Forbidden | {request.remote_addr}"}), 403  # Block external access
    return list_routes(app)


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200


@app.route("/streams/m3u", methods=["GET"])
def get_m3u():
    with open(data_dir / 'M3U8.json', 'r') as f:
        m3u8_links = json.loads(f.read())

    m3u_content = "#EXTM3U\n"

    for channel_name, stream_url in m3u8_links.items():
        m3u_content += f"#EXTINF:-1,{channel_name}\n"
        m3u_content += f"{stream_url}\n"

    return Response(m3u_content, mimetype="audio/x-mpegurl", content_type="application/x-mpegurl")


set_webhook()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port, debug=True)

import requests
from common.my_logger import logger
import threading
import json
import time
import redis


class TelegramHandlerManager:
    def __init__(self, **kwargs):
        self.redis_client = None
        self.api_url = None
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.handler_cache = {}
        logger.info('TelegramHandlerManager initialized')
        threading.Thread(target=self.outgoing_worker, daemon=True).start()

    def send_message(self, chat_id, message, inline_keyboard=None, **kwargs):
        payload = {"chat_id": chat_id, "text": message, **kwargs}
        if inline_keyboard:
            payload["reply_markup"] = json.dumps({"inline_keyboard": inline_keyboard, "resize_keyboard": True})
        r = requests.post(f"{self.api_url}/sendMessage", json=payload)

    def ack_callback(self, callback_id, text, **kwargs):
        payload = {"callback_query_id": callback_id, "text": text, "show_alert": False, **kwargs}
        r = requests.post(f"{self.api_url}/answerCallbackQuery", json=payload)

    def outgoing_worker(self):
        while True:
            try:
                messages = self.redis_client.xread({"telegram_outgoing": "$"}, count=None,
                                                   block=0)  # Block until message arrives
                for stream, message_list in messages:
                    for message_id, data in message_list:
                        chat_id = data["chat_id"]
                        msg_text = data["message"]
                        inline_keyboard = json.loads(data.get("inline_keyboard", "null"))
                        self.send_message(chat_id, msg_text, inline_keyboard)
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
                logger.warn(f"Redis connection lost: {e}. Retrying in 5 seconds...")
                time.sleep(5)

    def store_message(self, data):
        chat_id = text = callback_id = None
        if (key := "message") in data or (key := "channel_post") in data:
            chat_id = data[key].get("chat", {}).get("id")
            text = data.get(key, {}).get("text")

        elif "callback_query" in data:
            callback_query = data["callback_query"]
            chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
            callback_id = callback_query.get("id")
            self.ack_callback(callback_id, text="Processing...")
            text = f"/{callback_query["message"]["text"].lower()} {callback_query.get("data", "").lower()}"

        if chat_id and text:
            self.redis_client.xadd("telegram_incoming",
                                   {"chat_id": chat_id, "message": text}, maxlen=1000)
            self.redis_client.publish(f"{chat_id}", text)


if __name__ == '__main__':
    ...

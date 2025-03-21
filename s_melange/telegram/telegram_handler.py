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

    def send_message(self, chat_id, message, **kwargs):
        payload = {"chat_id": chat_id, "text": message, **kwargs}
        r = requests.post(f"{self.api_url}/sendMessage", json=payload)

    def outgoing_worker(self):
        while True:
            try:
                messages = self.redis_client.xread({"telegram_outgoing": "$"}, None, 0)  # Block until message arrives
                for stream, message_list in messages:
                    for message_id, data in message_list:
                        chat_id = data["chat_id"]
                        msg_text = data["message"]
                        self.send_message(chat_id, msg_text)
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
                logger.warn(f"Redis connection lost: {e}. Retrying in 5 seconds...")
                time.sleep(5)

    def store_message(self, data):
        chat_id = text = None
        if (key := "message") in data or (key := "channel_post") in data:
            chat_id = data[key].get("chat", {}).get("id")
            text = data.get(key, {}).get("text")
        if chat_id and text:
            self.redis_client.xadd("telegram_incoming", {"chat_id": chat_id, "message": text}, maxlen=1000)
            self.redis_client.publish(f"{chat_id}", text)


if __name__ == '__main__':
    ...

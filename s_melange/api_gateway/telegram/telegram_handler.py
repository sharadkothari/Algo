import json
import asyncio
import httpx
import redis.exceptions
from common.my_logger import logger


class TelegramHandlerManager:
    def __init__(self, **kwargs):
        self.redis_client = None
        self.api_url = None
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.client = httpx.AsyncClient()
        self._task = asyncio.create_task(self.outgoing_worker())
        logger.info('TelegramHandlerManager initialized (async)')

    async def send_message(self, chat_id, message, inline_keyboard=None, **kwargs):
        payload = {"chat_id": chat_id, "text": message, **kwargs}
        if inline_keyboard:
            payload["reply_markup"] = {"inline_keyboard": inline_keyboard, "resize_keyboard": True}
        try:
            await self.client.post(f"{self.api_url}/sendMessage", json=payload)
        except httpx.RequestError as e:
            logger.error(f"Failed to send Telegram message: {e}")

    async def ack_callback(self, callback_id, text, **kwargs):
        payload = {"callback_query_id": callback_id, "text": text, "show_alert": False, **kwargs}
        try:
            await self.client.post(f"{self.api_url}/answerCallbackQuery", json=payload)
        except httpx.RequestError as e:
            logger.error(f"Failed to ack callback: {e}")

    async def outgoing_worker(self):
        logger.info("Starting Telegram outgoing worker loop...")
        while True:
            try:
                messages = await self.redis_client.xread({"telegram_outgoing": "$"}, block=0)
                for stream, message_list in messages:
                    for _, data in message_list:
                        chat_id = data["chat_id"]
                        msg_text = data["message"]
                        inline_keyboard = json.loads(data.get("inline_keyboard", "null"))
                        await self.send_message(chat_id, msg_text, inline_keyboard)
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
                logger.warning(f"Redis connection lost: {e}. Retrying in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error in outgoing_worker: {e}")
                await asyncio.sleep(5)

    async def store_message(self, data):
        chat_id = text = None
        if (key := "message") in data or (key := "channel_post") in data:
            chat_id = data[key].get("chat", {}).get("id")
            text = data.get(key, {}).get("text")

        elif "callback_query" in data:
            callback_query = data["callback_query"]
            chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
            callback_id = callback_query.get("id")
            await self.ack_callback(callback_id, text="Processing...")
            text = f"/{callback_query['message']['text'].lower()} {callback_query.get('data', '').lower()}"

        if chat_id and text:
            await self.redis_client.xadd("telegram_incoming",
                                         {"chat_id": chat_id, "message": text}, maxlen=1000)
            await self.redis_client.publish(str(chat_id), text)

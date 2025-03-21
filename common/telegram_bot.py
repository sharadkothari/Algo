from common.config import redis_host, redis_port, redis_db
import redis
import threading
from common.my_logger import logger


class TelegramBot:

    def __init__(self, chat_id, consumer_name):
        self.chat_id = chat_id
        self.consumer_name = consumer_name
        self.outgoing_stream = "telegram_outgoing"
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe(**{f"{self.chat_id}": self.process_messages})
        pubsub.run_in_thread(sleep_time=1)

    def process_messages(self, message):
        ...

    def send(self, message, chat_id=None):
        chat_id = chat_id or self.chat_id
        self.redis_client.xadd(self.outgoing_stream, {"chat_id": chat_id, "message": message}, maxlen=1000)


class TelegramBotMain(TelegramBot):
    def __init__(self):
        super().__init__(chat_id=387589523, consumer_name="main")

    def process_messages(self, message):
        self.send(f"got: {message['data']}")


class TelegramBotService(TelegramBot):

    def __init__(self):
        super().__init__(chat_id=-1002340369818, consumer_name="service")

    def process_messages(self, message):
        self.send(f"got: {message['data']}")


if __name__ == "__main__":
    tbot = TelegramBotService()
    tbot.send('123')
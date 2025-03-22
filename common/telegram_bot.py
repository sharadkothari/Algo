from common.config import redis_host, redis_port, redis_db
import redis
import threading
from common.my_logger import logger


class TelegramBot:
    _instances = {}  # Store single instances per chat_id

    def __new__(cls, chat_id, consumer_name):
        """Ensure only one instance per chat_id exists."""
        if chat_id not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[chat_id] = instance
        return cls._instances[chat_id]

    def __init__(self, chat_id, consumer_name):
        """Prevent re-initialization if instance already exists."""
        if hasattr(self, "initialized"):
            return  # Avoid re-initialization

        self.chat_id = chat_id
        self.consumer_name = consumer_name
        self.outgoing_stream = "telegram_outgoing"
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe(**{f"{self.chat_id}": self.process_messages})
        pubsub.run_in_thread(sleep_time=1)

        self.initialized = True

    def process_messages(self, message):
        ...

    def send(self, message, chat_id=None):
        chat_id = chat_id or self.chat_id
        self.redis_client.xadd(self.outgoing_stream, {"chat_id": chat_id, "message": message}, maxlen=1000)


class TelegramBotMain(TelegramBot):
    consumer_name = "main"
    chat_id = 387589523

    def __new__(cls):
        return super().__new__(cls, cls.chat_id, cls.consumer_name)

    def __init__(self):
        super().__init__(chat_id=self.chat_id, consumer_name=self.consumer_name)

    def process_messages(self, message):
        self.send(f"got: {message['data']}")


class TelegramBotService(TelegramBot):
    consumer_name = "service"
    chat_id = -1002340369818

    def __new__(cls):
        return super().__new__(cls, cls.chat_id, cls.consumer_name)

    def __init__(self):
        super().__init__(chat_id=self.chat_id, consumer_name=self.consumer_name)

    def process_messages(self, message):
        self.send(f"got: {message['data']}")


class TelegramBotStocks(TelegramBot):

    consumer_name = "stocks"
    chat_id = -4626518827

    def __new__(cls):
        return super().__new__(cls, cls.chat_id, cls.consumer_name)

    def __init__(self):
        super().__init__(chat_id=self.chat_id, consumer_name=self.consumer_name)

    def process_messages(self, message):
        match message["data"].lower():
            case '/chat_id':
                text = f'chat_id: {self.chat_id}'
            case _:
                text = f'got: {message['data']}'
        self.send(text)


if __name__ == "__main__":
    tbot = TelegramBotService()
    tbot.send('123')

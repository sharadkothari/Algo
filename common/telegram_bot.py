from common.config import get_redis_client, url_docker_db
import redis
import threading
from common.my_logger import logger
import re
import requests
import json


class TelegramBot:
    _instances = {}  # Store single instances per chat_id

    def __new__(cls, chat_id, consumer_name, send_only=False):
        """Ensure only one instance per chat_id exists."""
        if chat_id not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[chat_id] = instance
        return cls._instances[chat_id]

    def __init__(self, chat_id, consumer_name, send_only=False):
        """Prevent re-initialization if instance already exists."""
        if hasattr(self, "initialized"):
            return  # Avoid re-initialization

        self.chat_id = chat_id
        self.consumer_name = consumer_name
        self.outgoing_stream = "telegram_outgoing"
        self.redis_client = get_redis_client()
        if not send_only:
            self.pubsub = self.redis_client.pubsub()
            self.pubsub.unsubscribe(f"{self.chat_id}")
            self.pubsub.subscribe(f"{self.chat_id}")
            self.initialized = True
            threading.Thread(target=self.listen_messages, daemon=True).start()

    def listen_messages(self):
        try:
            for message in self.pubsub.listen():
                if message["type"] == "message":  # Only process actual messages
                    self.process_messages(message)
        except Exception as e:
            logger.info(f"Listener error for chat_id {self.chat_id}: {e}")
        finally:
            self.pubsub.close()

    def process_messages(self, message):
        ...

    def send(self, message, inline_keyboard=None, chat_id=None):
        chat_id = chat_id or self.chat_id
        self.redis_client.xadd(self.outgoing_stream, {"chat_id": chat_id, "message": message,
                                                      "inline_keyboard": json.dumps(inline_keyboard), }, maxlen=1000)


class TelegramBotMain(TelegramBot):
    consumer_name = "main"
    chat_id = 387589523

    def __new__(cls, send_only=False):
        return super().__new__(cls, cls.chat_id, cls.consumer_name, send_only=send_only)

    def __init__(self, send_only=False):
        super().__init__(chat_id=self.chat_id, consumer_name=self.consumer_name, send_only=send_only)

    def process_messages(self, message):
        def get_service_data():
            self.send(f"main: {message['data']}")


class TelegramBotService(TelegramBot):
    consumer_name = "service"
    chat_id = -1002340369818

    def __new__(cls, send_only=False):
        return super().__new__(cls, cls.chat_id, cls.consumer_name, send_only=send_only)

    def __init__(self, send_only=False):
        super().__init__(chat_id=self.chat_id, consumer_name=self.consumer_name, send_only=send_only)
        self.pattern = r"^/(start|stop) (\S+)"
        self.status_icon = {"running": "🟢", "exited": "🔴"}
        self.service_data = self.get_service_data()
        self.send("starting...")

    def get_service_data(self):
        response = requests.get(f"{url_docker_db}/services")
        if response.ok:
            return {item["name"]: {"id": item["containerId"], "status": item["status"][0]} for item in
                    response.json()[0]}

        else:
            return {}

    def service_action(self, service, action):
        if service not in self.service_data:
            return f"service {service} not found"
        else:
            match action:
                case "status":
                    service_status = self.service_data[service]['status']
                    return f"{service} status: {service_status} {self.status_icon[service_status]}"
                case "start" | "stop":
                    service_status = self.service_data[service]['status']
                    check = {"start": "running", "stop": "exited"}
                    if check[action] == service_status:
                        return f"service {service} is already f{check[action]}"
                    else:
                        return requests.get(f"{url_docker_db}/{action}/{self.service_data[service]['id']}").text

    def send_menu(self, title, menu_items):
        inline_keyboard = [menu_items[i:i + 2] for i in range(0, len(menu_items), 2)]
        inline_keyboard = [[{"text": item, "callback_data": item} for item in row] for row in inline_keyboard]
        self.send(message=title, inline_keyboard=inline_keyboard)

    def process_messages(self, message):

        match text := message['data']:
            case "/menu":
                self.send_menu("MENU", ("start", "stop", "status"))

            case "/refresh":
                self.service_data = self.get_service_data()

            case cmd if re.match(r"^/(menu\s)?(start|stop|status)$", cmd):
                title = re.sub(r"^(/menu\s?|\s?/)", "", cmd).upper()
                self.service_data = self.get_service_data()
                service_list = [f"{key} {self.status_icon[value['status']]}" for key, value in
                                self.service_data.items()]
                self.send_menu(title, sorted(service_list))

            case cmd if re.match(r"^/status\b", cmd):
                self.send(self.service_action(service=cmd.split()[1], action="status"))

            case cmd if (m := re.match(r"^/(start|stop)\s+(\S+)", cmd)):
                action, service = m.groups()
                self.send(self.service_action(service=cmd.split()[1], action=action))

            case _:
                self.send(f"unknown service cmd: {message['data']}")


class TelegramBotStocks(TelegramBot):
    consumer_name = "stocks"
    chat_id = -4626518827

    def __new__(cls, send_only=False):
        return super().__new__(cls, cls.chat_id, cls.consumer_name, send_only=send_only)

    def __init__(self, send_only=False):
        super().__init__(chat_id=self.chat_id, consumer_name=self.consumer_name, send_only=send_only)

    def process_messages(self, message):
        match message["data"].lower():
            case '/chat_id':
                text = f'chat_id: {self.chat_id}'
            case _:
                text = f'stocks: {message['data']}'
        self.send(text)


if __name__ == "__main__":
    tbot = TelegramBotStocks(send_only=True)
    tbot.send('123')

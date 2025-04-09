from common.config import get_redis_client
from common.my_logger import logger
from common.telegram_bot import TelegramBotService
import threading
from common.base_service import BaseService
from pathlib import Path

module_name = Path(__file__).stem
redis_client = get_redis_client()
pubsub = redis_client.pubsub()
tbot_service = TelegramBotService(send_only=False)


class ServiceStatus(BaseService):

    def __init__(self):
        super().__init__(module_name)
        self.thread = threading.Thread(target=self.check, daemon=False)

    def start(self):
        self.thread.start()
        self.thread.join()

    @staticmethod
    def check():
        pubsub.psubscribe("__keyspace@0__:service:*")
        try:
            for msg in pubsub.listen():
                key = msg["channel"].split(":")[-1]  # Extract service key
                if msg["data"] == "hset":
                    status = redis_client.hget(f"service:{key}", "status")
                    if status:
                        status_emoji = "🟢" if status == "up" else "🔴"
                        message = f"{status_emoji} {key} : {status.upper()}"
                        logger.info(message)
                        tbot_service.send(message)
        except Exception as e:
            print(f"Listener error: {e}")
        finally:
            pubsub.close()  # Close connection to Redis
            print("Redis listener exited.")


if __name__ == '__main__':
    sc = ServiceStatus()
    sc.start()

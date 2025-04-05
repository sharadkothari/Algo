import signal
import socket
import atexit
import datetime as dt
from common.my_logger import logger
from common.config import get_redis_client

redis_client = get_redis_client()


class BaseService:
    def __init__(self, app_name: str):
        self.app_name = app_name
        self.hostname = socket.gethostname()
        self.on_start()

        # Setup signal handling
        signal.signal(signal.SIGTERM, self.on_stop)
        signal.signal(signal.SIGINT, self.on_stop)
        atexit.register(self.on_stop)  # in case of normal exit

    def on_start(self):
        container_id = socket.gethostname()
        redis_client.hset("services", self.app_name, f'{container_id}:0000')
        mapping = {"status": "up", "last_up": dt.datetime.now().isoformat()}
        redis_client.hset(f"service:{self.app_name}", mapping=mapping)
        logger.info(f"Started {self.app_name}")

    def on_stop(self, signum=None, frame=None):
        _ = signum, frame
        mapping = {"status": "dn", "last_dn": dt.datetime.now().isoformat()}
        redis_client.hset(f"service:{self.app_name}", mapping=mapping)
        logger.info(f"Stopped {self.app_name}")
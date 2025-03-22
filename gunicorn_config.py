import os
from common.my_logger import logger
import socket
from common.config import redis_host, redis_port, redis_db
import redis
import datetime

workers = 1
reload = True
keepalive = 5
# Enable threading for AP Scheduler compatibility
threads = 2

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:5000")

# Gunicorn log settings
accesslog = None  # log_file
errorlog = "-"
loglevel = "info"
capture_output = True

redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)


def on_starting(server):
    app_name = server.cfg.proc_name.split(':')[0]
    container_id = socket.gethostname()
    port = bind.split(':')[1]
    redis_client.hset("services", app_name, f'{container_id}:{port}')
    mapping = {"status": "up", "last_up": datetime.datetime.now().isoformat()}
    redis_client.hset(f"service:{app_name}", mapping=mapping)
    logger.info(f"Started {app_name}")


def on_exit(server):
    app_name = server.cfg.proc_name.split(':')[0]
    mapping = {"status": "dn", "last_dn": datetime.datetime.now().isoformat()}
    redis_client.hset(f"service:{app_name}", mapping=mapping)
    logger.info(f"Stopped {app_name}")

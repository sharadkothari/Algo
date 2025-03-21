import logging
import sys
import redis
from common.config import redis_host, redis_port, redis_db


class CustomFormatter(logging.Formatter):
    """Logging colored formatter with ANSI color codes."""

    COLORS = {
        logging.DEBUG: "\033[37m",  # White
        logging.INFO: "\033[90m",  # Grey
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[1m\033[31m"  # Bold Red
    }
    RESET = "\033[0m"

    def __init__(self, fmt):
        super().__init__()
        self.formatters = {
            level: logging.Formatter(color + fmt + self.RESET)
            for level, color in self.COLORS.items()
        }

    def format(self, record):
        return self.formatters.get(record.levelno, self.formatters[logging.INFO]).format(record)


class RedisStreamHandler(logging.Handler):
    """Logging handler to send logs to Redis Streams."""

    def __init__(self, stream_name="stocks", host=redis_host, port=redis_port, db=redis_db):
        super().__init__()
        self.stream_name = stream_name
        self.redis_client = redis.Redis(host=host, port=port, db=db, decode_responses=True)

    def emit(self, record):
        log_entry = self.format(record)
        self.redis_client.xadd(
            self.stream_name,
            {
                "level": record.levelname,
                "module": f"{record.module} | {record.lineno}",
                "message": record.getMessage(),
            },
            maxlen=1000
        )


# Logger setup
logger = logging.getLogger('stocks')
logger.handlers.clear()

log_format = '%(asctime)s | %(module)s#%(lineno)d | %(message)s'

# Console handler
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(CustomFormatter(fmt=log_format))

# Redis handler
redis_handler = RedisStreamHandler()

logger.addHandler(stream_handler)
logger.addHandler(redis_handler)
logger.setLevel(logging.DEBUG)

logging.getLogger('werkzeug').setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

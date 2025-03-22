from common.trading_hours import TradingHours
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.redis import RedisJobStore
from common.config import redis_host, redis_port, redis_db
import redis
import queue
import threading
import datetime as dt
import json
import time
from common.my_logger import logger
import signal


class TickingHandler:

    def __init__(self):
        self.candles_key = None
        self.tick_key = None
        self.tick_last_time: float | None = None
        self.candle_last_time: float | None = None
        self.alert_threshold_ticks = 10  # 10 seconds
        self.alert_threshold_candles = 20  # 10s + 10s buffer
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
        self.pubsub = self.redis_client.pubsub()
        self.pubsub.psubscribe(**{'__keyspace@0__:*': self.process_message})
        self.listener_thread = None
        self.task_queue = queue.Queue()
        self.pending_tasks = set()
        self.trading_hours = TradingHours(end_buffer=30)
        self.reset()
        self.scheduler = BackgroundScheduler()
        self.schedule_tasks()
        self.scheduler.start()
        signal.signal(signal.SIGINT, self.graceful_exit)  # Ctrl+C
        signal.signal(signal.SIGTERM, self.graceful_exit)  # Termination

    def graceful_exit(self, signum=None, frame=None):
        self.scheduler.shutdown()
        exit(0)

    def reset(self):
        date_str = dt.datetime.now().strftime("%Y%m%d")
        self.tick_key = f"tick:{date_str}"
        self.candles_key = f"candles{date_str}:NSE:NIFTY 50"
        self.tick_last_time: float | None = None
        self.candle_last_time: float | None = None
        self.pending_tasks = set()
        self.stop_listener()

    def worker(self):
        if not self.task_queue.empty():
            task = self.task_queue.get(block=False)
            self.pending_tasks.discard(task)  # Remove from pending set once processed
            if task == "tick":
                self.update_tick_time()
            elif task == "candles":
                self.update_candle_time()

    def add_task(self, task):
        if task not in self.pending_tasks:
            self.task_queue.put(task)
            self.pending_tasks.add(task)

    def start_listener(self):
        if self.listener_thread is None:
            self.listener_thread = self.pubsub.run_in_thread(sleep_time=1)

    def stop_listener(self):
        if self.listener_thread:
            self.listener_thread.stop()
            self.listener_thread = None

    def process_message(self, message):
        if message['type'] == 'pmessage':
            key = message['channel'].split(':', 1)[-1]
            if key == self.tick_key:
                self.add_task("tick")
            elif key == self.candles_key:
                self.add_task("candles")

    def update_tick_time(self):
        data = self.redis_client.hgetall(self.tick_key)
        if 'NSE:NIFTY 50' in data:
            self.tick_last_time = dt.datetime.fromisoformat(
                json.loads(data['NSE:NIFTY 50']).get('exchange_timestamp')).timestamp()

    def update_candle_time(self):
        candles: list = self.redis_client.zrange(self.candles_key, -1, -1, withscores=True)
        if candles:
            self.candle_last_time = candles[0][1]

    def check_alerts(self):
        current_time = time.time()
        alerts = {}

        if self.tick_last_time:
            tick_delay = current_time - self.tick_last_time
            if tick_delay > self.alert_threshold_ticks:
                alerts['tick'] = f"Tick delay exceeded: {tick_delay:.2f} seconds"
                self.redis_client.xadd('telegram_outgoing', {'chat_id': -4626518827, 'message': alerts['tick']})

        if self.candle_last_time:
            candle_delay = current_time - self.candle_last_time
            if candle_delay > self.alert_threshold_candles:
                alerts['candle'] = f"Candle delay exceeded: {candle_delay:.2f} seconds"
                self.redis_client.xadd('telegram_outgoing', {'chat_id': -4626518827, 'message': alerts['candle']})

    def schedule_tasks(self):
        if self.trading_hours.is_open():
            market_close_time = self.trading_hours.get_market_close_time()
            logger.info(f"Tracking ticks and candles until {market_close_time}")

            self.start_listener()
            self.scheduler.add_job(self.worker, "interval", seconds=1.5,
                                   id="task_queue_worker", end_date=market_close_time)
            self.scheduler.add_job(self.check_alerts, "interval", seconds=5,
                                   id="telegram_alerts", end_date=market_close_time)

            self.scheduler.add_job(self.schedule_tasks, "date",
                                   run_date=market_close_time + dt.timedelta(seconds=5),
                                   id="post_market_reset")
        else:
            next_open_time = dt.datetime.now() + self.trading_hours.time_until_next_open()
            logger.info(f"Rescheduling tracking ticking till {next_open_time:%d-%b-%Y %H:%M}")
            self.reset()
            self.scheduler.add_job(self.schedule_tasks, "date", run_date=next_open_time, id="reschedule_job")


if __name__ == "__main__":
    t = TickingHandler()

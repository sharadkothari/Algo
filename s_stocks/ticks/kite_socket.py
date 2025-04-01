import time
import threading
import pandas as pd
import redis
from kiteconnect import KiteTicker, KiteConnect
from common.config import data_dir, base_dir_prv, redis_host, redis_port, redis_db
import json
import datetime
import queue
from common.my_logger import logger
from common.trading_hours import TradingHours
from common.telegram_bot import TelegramBotStocks
import os
import signal

with open(data_dir / f'brokers.json', 'r') as f:
    broker_data = json.loads(f.read())

token_dir = base_dir_prv / 'config'
tbot = TelegramBotStocks()


class KiteSocket:

    def __init__(self, client_id: str = "YM3006"):
        logger.info(f'initializing kite socket: {client_id}')
        self.inst_symbol_dict = None
        self.client_id = client_id
        self.api_key = broker_data[client_id]['api_key']
        self.redis = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
        self.trading_hour = TradingHours(start_buffer=60)
        # self.rp = self.redis_client.pipeline()
        self.kws = None  # WebSocket instance
        self.kite = KiteConnect(self.api_key)
        self.thread_running = True  # Control the monitoring thread
        self.ticks = {}

        self.tick_queue = queue.Queue()
        self.is_running = False
        self.start()

    def start(self):
        threading.Thread(target=self.monitor, daemon=True).start()

    def get_access_token(self):
        return self.redis.get(f'access_token:{self.client_id}')

    def start_kiteticker(self, access_token):
        access_token = access_token if access_token else self.get_access_token()
        self.kws = KiteTicker(self.api_key, access_token)
        self.kite.set_access_token(access_token)

        def on_connect(ws, response):
            logger.info(f"WebSocket connected: {response}")
            tbot.send("WebSocket connected")
            if self.inst_symbol_dict is None:
                self.inst_symbol_dict = self.get_inst()
            tokens = list(self.inst_symbol_dict)
            ws.subscribe(tokens)
            ws.set_mode(ws.MODE_FULL, tokens)

        def on_ticks(ws, ticks):
            _ = ws
            cur_tick = {self.inst_symbol_dict.get(tick["instrument_token"], "NA"): tick for tick in ticks}
            self.tick_queue.put(cur_tick)
            self.ticks |= cur_tick

        def on_close(ws, code, reason):
            _ = code
            logger.info(f"WebSocket closed: {reason}")
            ws.stop_retry()

        def on_error(ws, code, reason):
            _ = ws
            _ = code
            logger.error(f"WebSocket Error: {reason}")

        def on_reconnect(ws, attempts):
            _ = ws
            logger.info(f"Reconnecting... Attempt {attempts}")

        def on_noreconnect(ws):
            _ = ws
            logger.info("Reconnect failed. Exiting.")

        # Define WebSocket event handlers
        self.kws.on_connect = on_connect
        self.kws.on_ticks = on_ticks
        self.kws.on_close = on_close
        self.kws.on_error = on_error
        self.kws.on_reconnect = on_reconnect
        self.kws.on_noreconnect = on_noreconnect

        # Start WebSocket in a separate thread
        # threading.Thread(target=self.kws.connect, kwargs={"threaded": True}, daemon=True).start()
        self.kws.connect(threaded=True)
        self.thread_running = True  # Control the monitoring thread

    def monitor(self):

        def suspend_ticker():
            if not self.trading_hour.is_open():
                seconds_until_open = self.trading_hour.time_until_next_open().total_seconds()
                next_open_time = now + datetime.timedelta(seconds=seconds_until_open)
                self.stop()
                logger.info(
                    f'suspending ticker till {next_open_time:%d-%b-%Y %H:%M} | {seconds_until_open:.0f} seconds')
                time.sleep(seconds_until_open)
                self.restart_program()  # needed due to Kiteticker uses twisted

        def start_ticker():
            if not self.is_running:
                if access_token := self.get_access_token():
                    logger.info(f"starting ticker")
                    self.start_kiteticker(access_token)
                    self.is_running = True

        def update_redis():
            if cur_queue:
                try:
                    with self.redis.pipeline() as pipe:
                        hash_key = f'tick:{date_str}'
                        list_key = 'ticks'
                        for tick in cur_queue:
                            pipe.lpush(list_key, json.dumps(tick, default=lambda x: x.isoformat()))
                            for key, value in tick.items():
                                pipe.hset(hash_key, key, json.dumps(value, default=lambda x: x.isoformat()))
                        pipe.expire(hash_key, 24 * 60 * 60)
                        pipe.expire(list_key, 24 * 60 * 60)
                        pipe.execute()
                except redis.RedisError as e:
                    logger.error(f"Redis pipeline execution failed: {e}")

        while True:
            now = datetime.datetime.now()
            date_str = datetime.date.today().strftime('%Y%m%d')
            cur_queue = [self.tick_queue.get() for _ in range(len(self.tick_queue.queue))]
            update_redis()
            suspend_ticker()
            start_ticker()

    @staticmethod
    def restart_program():
        """Restart the current process"""
        logger.info("Restarting Flask service for a new session...")
        # os.execv(sys.executable, ['python'] + sys.argv)  # Restart the Python process
        os.kill(os.getppid(), signal.SIGHUP)
        time.sleep(20)

    def stop(self):
        if self.kws:
            self.kws.close()
        self.is_running = False
        self.inst_symbol_dict = None

    def get_inst(self):
        try:
            df_raw = pd.DataFrame(self.kite.instruments())
            logger.info(f"Downloaded {len(df_raw)} kite instruments")
        except Exception as e:
            logger.info(f"Error fetching instruments: {e}")
            return {}
        else:
            idx_symbol = ["NIFTY 50", "SENSEX", "NIFTY BANK", "NIFTY NEXT 50", "NIFTY MIDCAP 150", "NIFTY SMLCAP 250",
                          'INDIA VIX']
            df_idx = df_raw[df_raw.segment.isin(["INDICES"]) & df_raw.tradingsymbol.isin(idx_symbol)]

            name_list = ['NIFTY', 'SENSEX', 'BANKNIFTY']
            exchange_list = ['NFO', 'BFO']

            df_derivative = df_raw[df_raw['name'].isin(name_list) & df_raw['exchange'].isin(exchange_list)]
            min_dates = df_derivative.groupby('name')['expiry'].min()
            df_derivative = df_derivative[df_derivative['expiry'].isin(sorted(set(min_dates))[:2])]
            df_concat = pd.concat([df_idx, df_derivative], ignore_index=True)
            df_concat['symbol'] = df_concat['exchange'] + ":" + df_concat['tradingsymbol']

            df_dict = df_concat.set_index('instrument_token')['symbol'].to_dict()
            return df_dict


if __name__ == "__main__":
    kq = KiteSocket()

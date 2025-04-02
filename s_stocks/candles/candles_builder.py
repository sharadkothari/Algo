import threading
import datetime
import json
import time
import redis
from common.my_logger import logger
from common.config import redis_host, redis_port, redis_db
from common.trading_hours import TradingHours


class Candles:
    EXPIRY_TIME = 86400  # 1 day in seconds

    def __init__(self):
        self.timeframe = 3  # seconds
        self.timestamp_field = 'exchange_timestamp'
        self.in_progress_candles = {}  # Holds active candles
        self.completed_candles = {}  # Holds candles ready to upload
        self.lock = threading.Lock()
        self.trading_hours = TradingHours(end_buffer=30)

        self.redis = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
        self.pipe = self.redis.pipeline()
        threading.Thread(target=self.upload_candle, daemon=True).start()
        threading.Thread(target=self.build_candles, daemon=True).start()

    def check_market_status(self, log_message=True):
        if not self.trading_hours.is_open():
            wait_time = self.trading_hours.time_until_next_open().total_seconds()
            next_open_time = datetime.datetime.now() + datetime.timedelta(seconds=wait_time)
            if log_message:
                logger.info(
                    f"Resetting candles and suspending till {next_open_time:%d-%b-%Y %H:%M} | {wait_time:.0f}sec")
            self.reset()
            time.sleep(wait_time)  # Wait until the market reopens
            if log_message:
                logger.info(f"Candles resuming...")

    def build_candles(self):
        while True:
            self.check_market_status()
            tick = self.redis.brpop(["ticks"], timeout=10)
            if tick is not None:
                self.process_tick(json.loads(tick[1]))

    def process_tick(self, tick):
        for symbol, symbol_tick in tick.items():
            timestamp_value = symbol_tick.get(self.timestamp_field)
            if not timestamp_value:
                continue

            timestamp_value = datetime.datetime.fromisoformat(timestamp_value)
            if timestamp_value.year <= 1970 or timestamp_value.time() <= self.trading_hours.start:
                continue

            timestamp = int(timestamp_value.timestamp())
            candle_time = timestamp - (timestamp % self.timeframe)
            last_price = symbol_tick.get('last_price', None)
            current_volume_traded = symbol_tick.get('volume_traded', 0)
            new_candle = False

            if symbol not in self.in_progress_candles:
                self.in_progress_candles[symbol] = {}

            candle = self.in_progress_candles[symbol]

            if candle:
                prv_candle_time = next(iter(candle))
                if prv_candle_time != candle_time:
                    prv_candle = candle.pop(prv_candle_time, {})
                    prv_cumm_volume = prv_candle['cumm_volume']
                    candle.clear()
                    new_candle = True

                    with self.lock:
                        self.completed_candles.setdefault(symbol, {})[prv_candle_time] = prv_candle.copy()
                    # threading.Event().wait(0.1)
                else:
                    prv_cumm_volume = candle[candle_time]['cumm_volume'] - candle[candle_time]['volume']
            else:
                new_candle = True
                prv_cumm_volume = 0

            if new_candle:
                candle[candle_time] = {
                    'date': datetime.datetime.fromtimestamp(candle_time),
                    'open': last_price,
                    'high': last_price,
                    'low': last_price,
                }

            candle[candle_time].update({
                'high': max(last_price, candle[candle_time]['high']),
                'low': min(last_price, candle[candle_time]['low']),
                'close': last_price,
                'oi': symbol_tick.get('oi', 0),
                'volume': max(0, current_volume_traded - prv_cumm_volume),
                'cumm_volume': current_volume_traded,
            })

    def reset(self):
        with self.lock:
            self.in_progress_candles.clear()
            self.completed_candles.clear()

    def upload_candle(self):
        while True:
            self.check_market_status(log_message=False)
            time.sleep(self.timeframe)

            with self.lock:
                to_upload = {symbol: self.completed_candles.pop(symbol, {}) for symbol in list(self.completed_candles)}

            if not to_upload:
                continue

            try:
                list_key = 'underlying_candles'
                with self.redis.pipeline() as pipe:
                    for symbol, candles in to_upload.items():
                        for candle_time, candle in candles.items():
                            key = f"candles{datetime.datetime.fromtimestamp(candle_time).strftime('%Y%m%d')}:{symbol}"
                            candle["date"] = candle["date"].isoformat()
                            value = json.dumps(candle)
                            pipe.zadd(key, {value: candle_time})
                            pipe.expire(key, self.EXPIRY_TIME)
                            if symbol in ("NSE:NIFTY 50", "BSE:SENSEX"):
                                list_value = {"symbol": symbol, "date": candle['date'], 'close': candle['close']}
                                list_value = json.dumps(list_value)
                                pipe.lpush(list_key, list_value)

                    pipe.expire(list_key, 24 * 60 * 60)
                    pipe.execute()
            except redis.RedisError as e:
                logger.error(f"Redis pipeline execution failed: {e}")


if __name__ == '__main__':
    _candles = Candles()

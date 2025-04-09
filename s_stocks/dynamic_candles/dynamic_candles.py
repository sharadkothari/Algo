import redis
from common.expiry import Expiry
from common.my_logger import logger
from common.config import redis_host, redis_port, redis_db
import json
from common.trading_hours import TradingHours
import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
import signal
from pathlib import Path
from common.base_service import BaseService

module_name = Path(__file__).stem

class DynamicCandlesBuilder(BaseService):

    def __init__(self):
        super().__init__(module_name)
        self.redis = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
        self.pipe = self.redis.pipeline()
        self.trading_hours = TradingHours(end_buffer=30)
        self.underlying_map = {"NSE:NIFTY 50": "NN", "BSE:SENSEX": "SX"}
        self.expiry = {k: Expiry(v) for k, v in self.underlying_map.items()}
        self.scheduler = BlockingScheduler()
        self.schedule_tasks()
        signal.signal(signal.SIGINT, self.graceful_exit)  # Ctrl+C
        signal.signal(signal.SIGTERM, self.graceful_exit)  # Termination

    def schedule_tasks(self):
        if self.trading_hours.is_open():
            market_close_time = self.trading_hours.get_market_close_time()
            logger.info(f"Starting dynamic candles scheduler until {market_close_time}")
            self.scheduler.add_job(self.build, "interval", seconds=1.5, id="dynamic_candles", end_date=market_close_time)
            # NEW: Schedule `schedule_tasks()` to run immediately after market close
            self.scheduler.add_job(self.schedule_tasks, "date",
                                   run_date=market_close_time + datetime.timedelta(seconds=5),
                                   id="post_market_reset")
        else:
            next_open_time = datetime.datetime.now() + self.trading_hours.time_until_next_open()
            logger.info(f"Rescheduling dynamic candles till {next_open_time:%d-%b-%Y %H:%M}")
            self.reset()
            self.scheduler.add_job(self.schedule_tasks, "date", run_date=next_open_time, id="reschedule_job")

    def graceful_exit(self, signum=None, frame=None):
        self.scheduler.shutdown()
        exit(0)

    def build(self):
        underlying_candle = self.redis.rpop("underlying_candles")
        if underlying_candle is not None:
            self.process_underlying_candle(json.loads(underlying_candle))

    def reset(self):
        self.redis.delete("underlying_candles")

    def process_underlying_candle(self, candle):
        underlying, date_iso, close = candle["symbol"], candle["date"], candle["close"]
        date = datetime.datetime.fromisoformat(date_iso)
        option_symbols, key_prefix = self.generate_option_symbols(date=date, underlying=underlying, close=close)
        matching_candles = (self.fetch_matching_candles(option_symbols, date))
        self.store_dynamic_candles(date_iso=date_iso, matching_candles=matching_candles, key_prefix=key_prefix)

    def generate_option_symbols(self, date, underlying, close):
        strike_width = self.expiry[underlying].get_strike_width()
        derivative_exchange = self.expiry[underlying].get_derivative_exchange()
        expiry_str = self.expiry[underlying].get_exp_str(date.date())
        key_prefix = f"candles{date:%Y%m%d}:{derivative_exchange}:{expiry_str}"

        atm_price = int(round(close / strike_width) * strike_width)
        option_symbols = []
        for opt_type in ["PE", "CE"]:
            for strike_ix in range(-1, 26):  # ITM (-1) to OTM (25)
                strike = atm_price + (strike_ix * strike_width * {"PE": -1, "CE": 1}[opt_type])
                option_symbols.append(
                    (f"d{strike_ix}{opt_type}", strike,
                     f"{key_prefix}{strike}{opt_type}"))

        return option_symbols, key_prefix

    def fetch_matching_candles(self, option_symbols, date):
        timestamp = date.timestamp()
        for _, __, symbol in option_symbols:
            self.pipe.zrevrangebyscore(symbol, timestamp, "-inf", start=0, num=1)
        results = self.pipe.execute()
        return {strike_ix: (strike, data[0] if data else None) for (strike_ix, strike, symbol), data in
                zip(option_symbols, results)}

    def store_dynamic_candles(self, date_iso, matching_candles, key_prefix):
        for strike_ix, strike_data in matching_candles.items():
            strike, data = strike_data
            if data is not None:
                data = json.loads(data)
                data["date"] = date_iso
                data['strike'] = strike
                data = json.dumps(data)
                key = f"{key_prefix}{strike_ix}"
                timestamp = int(datetime.datetime.fromisoformat(date_iso).timestamp())
                self.pipe.zadd(key, {data: timestamp})  # Store with timestamp
                self.pipe.expire(key, 24 * 60 * 60)
        self.pipe.execute()


if __name__ == '__main__':
    dc = DynamicCandlesBuilder()
    dc.scheduler.start()

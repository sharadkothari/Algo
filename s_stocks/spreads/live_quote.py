import pandas as pd
import datetime as dt
from common.expiry import Expiry
import redis
from common.config import redis_host, redis_port, redis_db
import json


class LiveQuote:

    def __init__(self):
        self.date = dt.date.today()
        self.redis = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
        self.underlying = {i: Expiry(i) for i in ("NN", "SX")}

    def quote(self, uix, opt_type=None, strike=None, **kwargs):
        date_str = self.date.strftime('%Y%m%d')
        dd = self.underlying[uix].get_derivative_data()
        exp = self.underlying[uix]
        if opt_type is None:
            redis_key = f'candles{date_str}:{dd["exchange"]}:{dd["underlying"]}'
        else:
            redis_key = f'candles{date_str}:{dd["derivative_exchange"]}:{exp.get_exp_str(self.date)}{strike}{opt_type}'
        redis_data: list = self.redis.zrange(redis_key, 0, -1)
        if redis_data:
            df = pd.DataFrame(map(json.loads, redis_data))
            df['date'] = pd.to_datetime(df.date)
            return df


if __name__ == '__main__':
    lq = LiveQuote()
    _df = lq.quote('SX', "CE", "d0")

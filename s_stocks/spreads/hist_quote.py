import pandas as pd
import datetime as dt
from common.expiry import Expiry
from common.config import parquet_dir
import os
import time
from common.my_logger import logger

_ = logger


class HistQuote:

    def __init__(self):
        self.date = None
        self.df = None
        self.exp_str = None
        self.underlying = {i: Expiry(i) for i in ("NN", "SX")}

    def set_date(self, date: dt.date):
        self.date = date
        self.exp_str = date.strftime("%Y%m%d")
        self.df = self._load_parquet_file()
        if self.df is not None:
            self.df = pd.concat([self.df, self.get_dynamic_strikes()], ignore_index=True)

    def _load_parquet_file(self):
        dfs = []
        for k, v in self.underlying.items():
            dd = v.get_derivative_data()
            exp_str = v.get_exp_str(self.date)
            file = f'{parquet_dir}/{dd["file_initial"]}_{self.date.strftime("%Y%m%d")}.parquet'
            if os.path.isfile(file):
                df = pd.read_parquet(file)
                df = df[(df.ticker == dd["underlying"]) |
                        (df.ticker.str.startswith(exp_str))]
                df['strike'] = df.ticker[df.ticker.str[-2:].isin(['CE', 'PE'])].str[len(exp_str):-2]
                dfs.append(df)

        if dfs:
            return pd.concat(dfs, ignore_index=True)

    def get_dynamic_strikes(self):
        dfs = []
        strike_map = {"PE": -1, "CE": 1}

        for k, v in self.underlying.items():
            dd = v.get_derivative_data()
            exp_str = v.get_exp_str(self.date)
            strike_width = dd['strike_width']

            udf = self.df[self.df.ticker == dd['underlying']][['date', 'close']].rename(columns={'close': 'underlying'})
            udf['ATM'] = (round(udf.underlying / strike_width) * strike_width).astype(int)

            for opt_type, direction in strike_map.items():
                for strike_ix in range(-1, 26):
                    strike_diff = strike_ix * strike_width * direction
                    udf["ticker"] = exp_str + (udf["ATM"] + strike_diff).astype(str) + opt_type
                    udf["new_ticker"] = exp_str + f"d{strike_ix}" + opt_type
                    dfs.append(udf[["date", "ticker", "new_ticker"]])

        if dfs:
            return (pd.concat(dfs, ignore_index=True)
                    .merge(self.df, how='left', on=['date', "ticker"])
                    .drop(columns=["ticker"])
                    .rename(columns={"new_ticker": "ticker"}))

    def quote(self, uix, opt_type=None, strike=None, **kwargs):
        _ = kwargs
        if self.df is not None:
            exp = self.underlying[uix]
            if opt_type is None:
                return self.df[self.df.ticker == exp.get_derivative_data()["underlying"]]
            elif strike is not None:
                ticker = f'{exp.get_exp_str(self.date)}{strike}{opt_type}'
                return self.df[self.df.ticker == ticker]


if __name__ == '__main__':
    q = HistQuote()
    start = time.time()
    q.set_date(dt.date(2025, 3, 13))
    print(time.time() - start)

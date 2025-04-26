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

    def get_option_chain(self, timestamp, underlying, ratio):
        # Filter and make a copy
        df = self.df[(self.df['date'] == pd.to_datetime(timestamp)) & self.df['ticker'].str.startswith(underlying)].copy()

        # Now safely extract suffix components
        df[['strikeix_str', 'type']] = df['ticker'].str.extract(r'(d-?\d+)(CE|PE)$')

        # Drop rows where regex didn't match
        df = df.dropna(subset=['strikeix_str', 'type'])

        # Convert strikeix to integer
        df['strikeix'] = df['strikeix_str'].str.replace('d', '', regex=False).astype(int)

        # 4. Create separate PE and CE dataframes
        pe_df = df[df['type'] == 'PE'][['strikeix', 'strike', 'close']]
        ce_df = df[df['type'] == 'CE'][['strikeix', 'strike', 'close']]

        # Rename columns to avoid conflict after merge
        pe_df = pe_df.rename(columns={'strike': 'PE_Strike', 'close': 'PE_Close'})
        ce_df = ce_df.rename(columns={'strike': 'CE_Strike', 'close': 'CE_Close'})

        # 5. Merge PE and CE on strikeix
        option_chain = pd.merge(pe_df, ce_df, on='strikeix', how='outer').sort_values('strikeix')

        # 6.  Create shifted close columns to divide by
        option_chain['PE_Close_shift'] = option_chain['PE_Close'].shift(-ratio)
        option_chain['CE_Close_shift'] = option_chain['CE_Close'].shift(-ratio)

        # 7. Compute ratio columns
        option_chain[f'PE_R{ratio}'] = option_chain['PE_Close'] / option_chain['PE_Close_shift']
        option_chain[f'CE_R{ratio}'] = option_chain['CE_Close'] / option_chain['CE_Close_shift']

        # Drop helper columns
        option_chain.drop(columns=['PE_Close_shift', 'CE_Close_shift'], inplace=True)

        return option_chain


if __name__ == '__main__':
    q = HistQuote()
    q.set_date(dt.date(2025, 3, 13))
    oc = q.get_option_chain(timestamp="2025-03-13 12:20:00", underlying="SENSEX", ratio=5)
    print(oc)

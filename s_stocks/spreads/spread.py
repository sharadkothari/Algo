from dataclasses import dataclass
import pandas as pd
from s_stocks.spreads.hist_quote import HistQuote
from s_stocks.spreads.live_quote import LiveQuote
import datetime as dt
from common.expiry import Expiry
import numpy as np


@dataclass
class QuoteLeg:
    uix: str  # NN or SX
    strike: str
    opt_type: str
    multiplier: int
    df: pd.DataFrame


class Spread:
    def __init__(self, live: bool = False, date: dt.date = None):
        self.date = date or dt.date.today()
        self.live = live
        self.legs = []
        self.underlying = {i: Expiry(i) for i in ("NN", "SX")}

    @property
    def live(self):
        return self._live

    @live.setter
    def live(self, live):
        self._live = live
        if live:
            self.quote: LiveQuote = LiveQuote()
        else:
            self.quote: HistQuote = HistQuote()
            self.quote.set_date(date=self.date)

    def get_date(self):
        return dt.date.today() if self.live else self.date

    def change_date(self, date):
        if not self.live:
            self.date = date
            self.quote.set_date(date=self.date)

    def add_leg(self, uix, strike, opt_type, multiplier):
        kwargs = locals()
        kwargs.pop("self")
        df = self.quote.quote(**kwargs)
        self.legs.append(QuoteLeg(**(kwargs | {"df": df})))

    def update_df(self):
        for leg in self.legs:
            leg.df = self.quote.quote(uix=leg.uix, strike=leg.strike, opt_type=leg.opt_type)

    def compute_spread(self, by_option=False):
        if self.live:
            self.update_df()
        # Collect unique datetime values
        all_times = pd.concat([leg.df for leg in self.legs])["date"].unique()
        all_times = np.sort(pd.to_datetime(all_times))

        spread_df = {'all': pd.DataFrame(), 'pe': pd.DataFrame(), 'ce': pd.DataFrame()}

        for leg in self.legs:
            df = leg.df.copy()
            df.loc[:, ['open', 'high', 'low', 'close']] *= leg.multiplier
            df = df.drop_duplicates(subset="date").set_index("date").reindex(all_times).ffill().infer_objects(
                copy=False)  # Align timestamps

            key = leg.opt_type.lower() if by_option else 'all'
            spread_df[key] = spread_df[key].add(df, fill_value=0) if not spread_df[key].empty else df
            if not by_option:
                self.add_vwap(spread_df[key])

        for k, df in spread_df.items():
            df.reset_index(inplace=True)

        return spread_df

    @staticmethod
    def add_vwap(df):
        vol = df['volume'].values
        price = (df['high'].values + df['low'].values) / 2
        cumulative_vol_price = np.add.accumulate(vol * price)
        cumulative_vol = np.add.accumulate(vol)
        safe_cumulative_vol = np.maximum(cumulative_vol, 0.1)
        df['vwap'] = cumulative_vol_price / safe_cumulative_vol

    def get_underlying_quote(self, uix):
        return self.quote.quote(uix)

    def get_static_strike(self, uix, time: dt.time, opt_type: str, strike: str):
        udf: pd.DataFrame = self.get_underlying_quote(uix)
        seek_row = udf.loc[udf.date == udf.loc[udf.date.dt.time <= time, 'date'].max()].close
        if len(seek_row) > 0:
            return self.underlying[uix].get_strike(price=seek_row.iloc[0], opt_type=opt_type, strike_ix=int(strike[1:]))


if __name__ == '__main__':
    s = Spread(live=False, date=dt.date(2025, 4, 22))
    s.add_leg("NN", "d0", "CE", 1)
    s.add_leg("NN", "d0", "PE", 1)
    dfs = s.compute_spread()

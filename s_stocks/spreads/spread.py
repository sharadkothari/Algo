from dataclasses import dataclass
import pandas as pd
from .hist_quote import HistQuote
from .live_quote import LiveQuote
import datetime as dt
from common.expiry import Expiry


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
        self.uq = {}  # underlying quote
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

    def add_leg(self, uix, strike, opt_type, multiplier):
        kwargs = locals()
        kwargs.pop("self")
        df = self.quote.quote(**kwargs)
        self.legs.append(QuoteLeg(**(kwargs | {"df": df})))

    def get_underlying_quote(self, uix):
        if uix not in self.uq:
            self.uq[uix] = self.quote.quote(uix)
        return self.uq[uix]

    def get_static_strike(self, uix, time: dt.time, opt_type: str, strike: str):
        udf: pd.DataFrame = self.get_underlying_quote(uix)
        seek_row = udf.loc[udf.date == udf.loc[udf.date.dt.time <= time, 'date'].max()].close
        if len(seek_row) > 0:
            return self.underlying[uix].get_strike(price=seek_row.iloc[0], opt_type=opt_type, strike_ix=int(strike[1:]))


if __name__ == '__main__':
    s = Spread(live=False, date=dt.date(2025, 3, 17))
    s.add_leg("NN", "d0", "CE", 1)
    s.add_leg("NN", "d0", "PE", 1)

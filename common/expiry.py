import json
import datetime
from common.config import data_dir
import numpy as np

class Expiry:
    def __init__(self, instrument):
        self.instrument = instrument
        self.expiry_days = self.load_json(file_name="expiry_days.json")
        self.holidays = self.load_json(file_name="nse_holidays.json")
        self.derivative_data = self.load_json(file_name="derivative_data.json")

    @staticmethod
    def load_json(file_name):
        with open(f"{data_dir}/{file_name}", "r") as f:
            return json.load(f)

    def get_expiry_day(self,  date: datetime.date = None):
        date = date or datetime.date.today()
        instrument_rules = self.expiry_days[self.instrument]
        applicable_rule = None
        for rule_date, weekday in sorted(instrument_rules.items(), key=lambda x: x[0], reverse=True):
            rule_date = datetime.datetime.strptime(rule_date, "%Y-%m-%d").date()
            if rule_date <= date:
                return weekday

    def get_expiry(self,  date: datetime.date = None) -> datetime.date:
        date = date or datetime.date.today()
        expiry_weekday = self.get_expiry_day(date=date)
        days_ahead = (expiry_weekday - date.weekday()) % 7
        expiry_date = date + datetime.timedelta(days=days_ahead)

        # Adjust for holidays / weekends
        while expiry_date.strftime("%Y-%m-%d") in self.holidays or expiry_date.weekday() in (5, 6):
            expiry_date -= datetime.timedelta(days=1)  # Move to previous business day

        return expiry_date

    def get_exp_str(self, date: datetime.date = None ) -> str:
        exp_date = self.get_expiry(date)
        next_exp_date = self.get_expiry(date + datetime.timedelta(days=7))
        derivative = self.derivative_data[self.instrument]['derivative_name']
        if exp_date.month != next_exp_date.month:
            return f'{derivative}{exp_date.year % 100}{exp_date.strftime("%b").upper()}'

        mth_wk = [1, 2, 3, 4, 5, 6, 7, 8, 9, 'O', 'N', 'D']
        return f'{derivative}{exp_date.year % 100}{mth_wk[exp_date.month - 1]}{exp_date.day:02d}'

    def get_strike_width(self):
        return self.derivative_data[self.instrument]['strike_width']

    def get_derivative_exchange(self):
        return self.derivative_data[self.instrument]['derivative_exchange']

    def get_derivative_data(self):
        return self.derivative_data[self.instrument]

    def get_strike(self, price, opt_type, strike_ix):
        strike_width = self.derivative_data[self.instrument]['strike_width']
        atm_price = int(round(price / strike_width) * strike_width)
        return atm_price + (strike_ix * strike_width * {"PE": -1, "CE": 1}[opt_type])

    def dte(self, date):
        holidays = [datetime.datetime.strptime(date, "%d-%b-%Y").date() for date in self.holidays]
        holidays = np.array(holidays, dtype='datetime64[D]')
        expiry_date = self.get_expiry(date)
        return np.busday_count(date, expiry_date, holidays=holidays)

    def underlying(self):
        return self.derivative_data[self.instrument]['underlying']

if __name__ == "__main__":
    e = Expiry("NN")
    print(e.dte(datetime.date(2025,3,26)))


from datetime import datetime, time, timedelta
import json
from common.config import data_dir


class TradingHours:

    def __init__(self, start_buffer=0, end_buffer=0):
        self.start = self.add_seconds(time(9, 15), -start_buffer)
        self.end = self.add_seconds(time(15, 30), end_buffer)
        self.holidays = self.load_holidays()

    @staticmethod
    def load_holidays():
        with open(f"{data_dir}/nse_holidays.json", "r") as f:
            return set(json.load(f))

    @staticmethod
    def add_seconds(time, seconds):
        dt_obj = datetime.combine(datetime.today(), time) + timedelta(seconds=seconds)
        return dt_obj.time()

    def is_holiday(self, date):
        return date.strftime("%Y-%m-%d") in self.holidays

    def is_open(self):
        now = datetime.now()
        if now.weekday() >= 5 or self.is_holiday(now):
            return False
        return self.start <= now.time() < self.end

    def get_market_close_time(self):
        return datetime.combine(datetime.now().date(), self.end)

    def time_until_close(self):
        now = datetime.now()
        if self.is_open():
            return datetime.combine(now.date(), self.end) - now

    def time_until_next_open(self):
        now = datetime.now()
        if now.time() < self.start and now.weekday() < 5 and not self.is_holiday(now):
            return datetime.combine(now.date(), self.start) - now

        next_day = now + timedelta(days=1)
        while next_day.weekday() >= 5 or self.is_holiday(next_day):
            next_day += timedelta(days=1)
        return datetime.combine(next_day.date(), self.start) - now


if __name__ == "__main__":
    th = TradingHours()
    print(th.time_until_next_open())

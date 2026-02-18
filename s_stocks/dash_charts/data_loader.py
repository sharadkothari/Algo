import datetime

from s_stocks.spreads.spread import Spread
from common.config import get_redis_client
from redis.commands.json.path import Path
import datetime as dt
from common.expiry import Expiry
from common_library.trading.trading_hours import TradingHours

redis_client = get_redis_client()


class ConfigPropertiesMixin:

    def __init__(self):
        self.config = None

    def get_default_config(self):
        return {
            'live': False,
            'uix': "NN",
            "by_option": False,
            'date': (dt.date.today()-dt.timedelta(days=1)).isoformat(),
            'track_time': {"start": "09:15", "end": "15:30"},
            "static_strike": False,
            'legs': [
                {'opt_type': 'PE', 'strike': "d0", 'multiplier': 1},
                {'opt_type': 'CE', 'strike': "d0", 'multiplier': 1}
            ]
        }

    @staticmethod
    def default_date():
        ...

    @property
    def columns(self):
        return [{'id': key, 'name': key} for key in self.get_default_config()['legs'][0]]

    @property
    def live(self):
        return self.config["live"]

    @property
    def uix(self):
        return self.config["uix"]

    @property
    def by_option(self):
        return self.config["by_option"]

    @property
    def txt_by_option(self):
        return ["Σ", "Ͽ"][int(self.by_option)]

    @property
    def date(self):
        return dt.datetime.fromisoformat(self.config["date"]).date()

    @property
    def track_time_start(self):
        return self.config.get("track_time", self.get_default_config()["track_time"])["start"]

    @property
    def track_time_end(self):
        return self.config.get("track_time", self.get_default_config()["track_time"])["end"]

    @property
    def txt_strike(self):
        return 'μ' if self.static_strike else 'η'

    @property
    def static_strike(self):
        return self.config.get("static_strike", False)

    @property
    def legs(self):
        return self.config.get("legs", False)


class DataLoader(ConfigPropertiesMixin):

    def __init__(self, app_id):
        super().__init__()
        self.config_key = "plotly:config:json"
        self.app_id = app_id
        self.spread = None
        self.expiry = None
        self.th = TradingHours()
        self.strategies = self.get_strategies()
        self.load_data()

    def load_data(self):
        json_config = redis_client.json().get(self.config_key, f"$.{self.app_id}")
        if json_config:
            cur_config = json_config[0]
        else:
            cur_config = self.get_default_config()
            self.store_data(cur_config)
        self.config = cur_config
        self.expiry = Expiry(self.uix)
        self.init_spread()

    def store_data(self, config):
        if not redis_client.exists(self.config_key):
            redis_client.json().set(self.config_key, Path.root_path(), {})
        redis_client.json().set(self.config_key, f"$.{self.app_id}", config)

    def init_spread(self):
        self.spread = Spread(live=self.config["live"],
                             date=dt.datetime.fromisoformat(self.config["date"]).date())
        self.set_spread_legs()

    def set_spread_legs(self):
        self.spread.legs = []
        for leg in self.config['legs']:
            if self.static_strike and leg['strike'][0] == "d":
                strike = self.spread.get_static_strike(uix=self.uix, opt_type=leg["opt_type"], strike=leg["strike"],
                                                       time=dt.datetime.strptime(self.track_time_start, '%H:%M').time())
            else:
                strike = leg['strike']
            self.spread.add_leg(**(leg | {"uix": self.config["uix"]} | {'strike': strike}))

    def toggle_uix(self):
        self.config["uix"] = {"NN": "SX", "SX": "NN"}[self.config["uix"]]
        self.set_spread_legs()
        self.redis_set("uix")
        self.expiry = Expiry(self.uix)

    def toggle_by_option(self):
        self.config["by_option"] ^= 1  # Toggles the value
        self.redis_set("by_option")

    def toggle_static_strike(self):
        self.config["static_strike"] = not self.config["static_strike"]
        self.redis_set("static_strike")
        self.set_spread_legs()

    def toggle_quote(self):
        self.config["live"] = not self.config["live"]
        self.redis_set("live")
        self.spread.live = self.config["live"]
        self.set_spread_legs()

    def change_date(self, delta=None, new_date=None):
        if not self.config["live"]:
            if new_date is not None:
                new_date = self.expiry.bus_day(date=new_date, delta=0)
            elif delta is not None:
                new_date = self.expiry.bus_day(date=self.config["date"], delta=delta)
            if new_date:
                self.config["date"] = new_date.isoformat()
                self.redis_set("date")
                self.spread.change_date(date=new_date)
                self.set_spread_legs()

    def update_legs(self, legs):
        self.config["legs"] = []
        for leg in legs:
            opt_type = f"{leg['opt_type'][0].upper()}E"
            if opt_type in ('PE', 'CE'):
                leg['opt_type'] = opt_type
                leg['strike'] = leg['strike'].lower()
                leg['multiplier'] = int(leg['multiplier'])
                self.config["legs"].append(leg)
        self.set_spread_legs()
        self.redis_set("legs")
        return self.config["legs"]

    def set_track_time(self, start, end):
        self.config["track_time"] = {"start": start, "end": end}
        self.redis_set("track_time")
        if self.static_strike:
            self.set_spread_legs()

    def redis_set(self, key):
        redis_client.json().set(self.config_key, f"$.{self.app_id}.{key}", self.config[key])

    @staticmethod
    def get_strategies():
        spread = {
            'ATM': [[0, 1]],
            'OTM': [[1, 1]],
            '10x1_15x-2': [[10, 1], [15, -2]],
            '8x1_11x-2': [[8, 1800], [11, -3600]],
        }
        strategy = {}
        for k, v in spread.items():
            strategy[k] = []
            for opt_type in ('PE', 'CE'):
                for i in v:
                    strategy[k].append({'opt_type': opt_type, 'strike': f"d{i[0]}", 'multiplier': i[1]})
        return strategy

    def apply_strategy(self, strategy):
        if strategy in self.strategies:
            self.update_legs(self.strategies[strategy])
            return True


if __name__ == "__main__":
    d = DataLoader(1)
    print(d.get_strategies())

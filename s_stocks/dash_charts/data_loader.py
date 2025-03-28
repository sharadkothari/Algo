import datetime

from s_stocks.spreads.spread import Spread
from common.config import get_redis_client
from redis.commands.json.path import Path
import datetime as dt
from common.expiry import Expiry

redis_client = get_redis_client()


class DataLoader:

    def __init__(self, app_id):
        self.config_key = "plotly:config:json"
        self.app_id = app_id
        self.static_strike = False
        self.config = None
        self.spread = None
        self.expiry = None
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

    @staticmethod
    def get_default_config():
        return {
            'live': False,
            'uix': "NN",
            "by_option": False,
            'date': dt.date.today().isoformat(),
            'legs': [
                {'opt_type': 'PE', 'strike': "d0", 'multiplier': 1},
                {'opt_type': 'CE', 'strike': "d0", 'multiplier': 1}
            ]
        }

    def init_spread(self):
        self.spread = Spread(live=self.config["live"],
                             date=dt.datetime.fromisoformat(self.config["date"]).date())
        self.set_spread_legs()

    def set_spread_legs(self):
        self.spread.legs = []
        for leg in self.config['legs']:
            self.spread.add_leg(**(leg | {"uix": self.config["uix"]}))

    def toggle_uix(self):
        self.config["uix"] = {"NN": "SX", "SX": "NN"}[self.config["uix"]]
        self.set_spread_legs()
        self.redis_set("uix")
        self.expiry = Expiry(self.uix)

    def toggle_by_option(self):
        self.config["by_option"] ^= 1  # Toggles the value
        self.redis_set("by_option")

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

    def redis_set(self, key):
        redis_client.json().set(self.config_key, f"$.{self.app_id}.{key}", self.config[key])

    @property
    def legs(self):
        return self.config["legs"]

    @property
    def columns(self):
        return [{'id': key, 'name': key} for key in self.get_default_config()['legs'][0]]

    @property
    def txt_strike(self):
        return 'η' if self.static_strike else 'μ'  # "eta" (η) / "μ" (mu)

    @property
    def txt_by_option(self):
        return ["Σ", "Ͽ"][int(self.by_option)]  # sigma & anti sigma

    @property
    def uix(self):
        return self.config.get("uix")

    @property
    def by_option(self):  # separate chart for opt_type
        return self.config.get("by_option", False)

    @property
    def date(self):
        return dt.datetime.fromisoformat(self.config["date"]).date()


if __name__ == "__main__":
    d = DataLoader(1)

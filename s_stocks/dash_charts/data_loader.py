from s_stocks.spreads.spread import Spread
from common.config import get_redis_client
from redis.commands.json.path import Path
import datetime as dt
from common.expiry import  Expiry
redis_client = get_redis_client()


class DataLoader:

    def __init__(self, app_id):
        self.config_key = "plotly:config:json"
        self.app_id = app_id
        self.by_option = False # separate chart for opt_type
        self.spread = None
        self.uix = None
        self.expiry = None
        self.load_data()

    def load_data(self):
        json_config = redis_client.json().get(self.config_key, f"$.{self.app_id}")
        if json_config:
            cur_config = json_config[0]
        else:
            cur_config = self.get_default_config()
            self.store_data(cur_config)
        self.uix = cur_config["uix"]
        self.expiry = Expiry(self.uix)
        self.init_spread(cur_config)

    def store_data(self, config):
        if not redis_client.exists(self.config_key):
            redis_client.json().set(self.config_key, Path.root_path(), {})
        redis_client.json().set(self.config_key, f"$.{self.app_id}", config)

    @staticmethod
    def get_default_config():
        return {
            'live': False,
            'uix': "NN",
            'date': dt.date.today().isoformat(),
            'legs': [
                {'opt_type': 'PE', 'strike': "d0", 'multiplier': 1},
                {'opt_type': 'CE', 'strike': "d0", 'multiplier': 1}
            ]
        }

    def init_spread(self, config):
        self.spread = Spread(live=config["live"],
                             date=dt.datetime.fromisoformat(config["date"]).date())
        for leg in config['legs']:
            self.spread.add_leg(**(leg | {"uix": config["uix"]}))


if __name__ == "__main__":
    d = DataLoader(1)

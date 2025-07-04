from common.utils import TimeCalc
from common.config import get_redis_client_v2, get_browser_profiles
from common.my_logger import logger
import os
from common.telegram_bot import TelegramBotService as TelegramBot
import time

tbot = TelegramBot(send_only=True)


class CommonToken:

    def __init__(self, client_ids: list, get_cookie_token, validate_token):
        self.client_ids = client_ids
        self.get_cookie_token = get_cookie_token
        self.validate_token = validate_token
        self.r = get_redis_client_v2(port_ix=1)
        tc = TimeCalc()
        self.expiry_ts = int(tc.next_6am().timestamp())
        self.browser_profiles = get_browser_profiles()
        self.extract_token()

    def store_token(self, client, token):
        self.r.expireat("browser_token", self.expiry_ts)
        self.r.hset('browser_token', client, token)

    def extract_token(self):
        logger.info(f"Getting tokens for | {self.client_ids}")

        for client in self.client_ids:
            token_stored = False
            profile = self.browser_profiles.get(client)
            if not profile:
                logger.warning(f"{client} | ❌ profile not found")
            else:
                try:
                    cookie_path = os.path.join(os.path.expanduser('~'),
                                               f'Library/Application Support/Microsoft Edge/{profile}/Cookies')
                    token = self.get_cookie_token(cookie_path)
                    if self.validate_token(token, client):
                        self.store_token(client, token)
                        logger.info(f"{client} | ✅ token stored")
                        token_stored = True
                    else:
                        logger.info(f"{client} | ❌ token expired")
                except Exception as e:
                    logger.warning(f"{client} | ❌ token not found / error: {str(e)}")
            if token_stored:
                tbot.send(f"{client} | ✅ token stored")
            else:
                tbot.send(f"{client} |  ❌ error")
            time.sleep(1)

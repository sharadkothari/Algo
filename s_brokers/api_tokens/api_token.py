import time
import json
import pyotp
import requests
from kiteconnect import KiteConnect
from common.utils import Encrypt
from common.my_logger import logger
from common.telegram_bot import TelegramBotStocks
from common.config import data_dir, get_redis_client
from apscheduler.schedulers.blocking import BlockingScheduler
import datetime as dt
import signal
from pathlib import Path
from common.base_service import BaseService

module_name = Path(__file__).stem

with open(data_dir / f'brokers.json', 'r') as f:
    broker_data = json.loads(f.read())

# Initialize Redis
redis_client = get_redis_client()
tbot = TelegramBotStocks(send_only=True)

# Zerodha Kite Login URLs
LOGIN_URL = "https://kite.zerodha.com/api/login"
TOTP_URL = "https://kite.zerodha.com/api/twofa"
SESSION_URL = "https://kite.zerodha.com/api/session/token"

# Zerodha Headers
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/x-www-form-urlencoded"
}


class KiteToken:
    def __init__(self):
        self.client_id = None
        self.password = None
        self.api_key = None
        self.api_secret = None
        self.otp_key = None
        self.redis_client = None

    def set_client_id(self, client_id: str):
        self.client_id = client_id
        self.redis_key = f"access_token_auto:{client_id}"
        enc = Encrypt(self.client_id)
        data = broker_data[client_id]
        for k, v in data.items():
            setattr(self, k, enc.decrypt(v))

    def get_request_token(self) -> str | None:
        session = requests.Session()

        # Step 1: Send Login Request
        login_payload = {"user_id": self.client_id, "password": self.password}
        login_response = session.post(LOGIN_URL, data=login_payload, headers={})

        if login_response.status_code != 200 or "request_id" not in login_response.json()['data']:
            logger.info(f"{self.client_id} | Login failed: {login_response.text}")
            return None

        request_id = login_response.json()['data']["request_id"]

        # Step 2: Submit TOTP for 2FA
        totp = pyotp.TOTP(self.otp_key).now()
        totp_payload = {"user_id": self.client_id, "request_id": request_id, "twofa_value": totp}
        totp_response = session.post(TOTP_URL, data=totp_payload, headers={})

        # Step 3: Extract request_token from redirect
        if totp_response.json()["status"] == "success":
            redirect_url = f"https://kite.zerodha.com/connect/login?v=3&api_key={self.api_key}"
            response = session.get(redirect_url, headers={}, allow_redirects=True)
            if "request_token=" in response.url:
                return response.url.split("request_token=")[1].split("&")[0]

    def get_access_token(self):
        kite = KiteConnect(api_key=self.api_key)
        try:
            request_token = self.get_request_token()
        except:
            request_token = None

        if request_token is None:
            logger.info("Failed to retrieve request token.")
            return False

        try:
            data = kite.generate_session(request_token, api_secret=self.api_secret)
            new_access_token = data["access_token"]
            stored_token = redis_client.get(self.redis_key)
            if stored_token is None or stored_token != new_access_token:
                redis_client.set(self.redis_key, new_access_token)
                logger.info(f"{self.client_id} | New access token updated: {new_access_token}")
                return True
            return False
        except Exception as e:
            logger.info(f"Error fetching access token: {e}")
            return False


class TokenScheduler(BaseService):

    def __init__(self):
        super().__init__(module_name)
        self.client_ids = ["RS5756", "YM3006", "MIM066"]
        self.retry_list = []
        self.kt = KiteToken()
        self.scheduler = BlockingScheduler()
        self.start_key = [22, 0, 2]  # start hour, start_minute, end_minute
        self.scheduler.add_job(self.daily_update, 'cron', hour=self.start_key[0],
                               minute=self.start_key[1], id='daily_scheduler')
        signal.signal(signal.SIGINT, self.graceful_exit)  # Ctrl+C
        signal.signal(signal.SIGTERM, self.graceful_exit)  # Termination

    def get_access_token(self):
        still_pending = []
        for client_id in self.retry_list:
            self.kt.set_client_id(client_id)
            success = self.kt.get_access_token()
            if not success:
                still_pending.append(client_id)

        self.retry_list = still_pending
        if not self.retry_list:
            msg = "All tokens fetched"
            logger.info(msg)
            tbot.send(msg)
            self.scheduler.remove_job('token_retry_job')
            self.scheduler.remove_job('finalize_token_job')

    def stop_retries(self):
        if self.retry_list:
            msg = f"Unable to get access tokens for {" | ".join(self.retry_list)}"
            logger.info(msg)
            tbot.send(msg)

    def daily_update(self):
        min_start = f"{self.start_key[1]}-{self.start_key[2]}"
        logger.info("starting daily update of access tokens...")
        self.retry_list = self.client_ids.copy()
        self.scheduler.add_job(self.get_access_token, 'cron', id='token_retry_job', hour=self.start_key[0],
                               minute=f"{self.start_key[1]}-{self.start_key[2]}", replace_existing=True)
        self.scheduler.add_job(self.stop_retries, 'cron', id='finalize_token_job', hour=self.start_key[0],
                               minute=self.start_key[2] + 1, )

    def graceful_exit(self, signum=None, frame=None):
        self.scheduler.shutdown()
        exit(0)


if __name__ == "__main__":
    ts = TokenScheduler()
    ts.scheduler.start()

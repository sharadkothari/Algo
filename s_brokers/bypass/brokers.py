from common.config import get_redis_client_v2
import aiohttp
import asyncio
from common.my_logger import logger
import json
from common.utils import Encrypt


class Broker:
    def __init__(self, userid: str, token, ticks: dict):
        self.name = None
        self.base_url = None
        self.userid = userid
        self.token = token
        self.ticks = ticks
        self._token_valid = False
        self._validate_task = None
        self._stop_event = asyncio.Event()
        self.r = None

    async def set_token(self):
        e = Encrypt(self.userid.lower())
        self.token = e.decrypt(await self.r.hget("browser_token", self.userid.lower()))

    @classmethod
    async def create(cls, userid: str, ticks=None):
        broker = cls(userid, None, ticks)
        broker.r = await get_redis_client_v2(asyncio=True, port_ix=1)
        await broker.set_token()
        broker._token_valid = await broker._do_validate_token()
        return broker

    def get_headers(self, params=None, prd_key=None):
        match self.name:
            case 'kite':
                headers = {'authorization': self.token}
                method = "get"
                kwargs = {'params': params}
                response_timeout = 20

            case 'shoonya':
                headers = {}
                method = "post"
                data = {'uid': self.userid.upper(), 'actid': self.userid.upper()}
                if prd_key is not None:
                    data['prd'] = prd_key
                data = f'jData={json.dumps(data)}&jKey={self.token}'
                kwargs = {'data': data}
                response_timeout = 20

            case 'neo':
                authorization = sid = None
                if self.token is not None:
                    authorization, sid = self.token.split("::")
                method = "post"
                headers = {'authorization': authorization, 'sid': sid}
                data = {'jData': json.dumps({"seg": "ALL", "exch": "ALL", "prod": "ALL"})}
                kwargs = {'data': data}
                response_timeout = 30

            case _:
                headers = {}
                method = "get"
                kwargs = {}
                response_timeout = 20

        return headers, method, kwargs, response_timeout

    async def get_response(self, path, params=None, prd_key=None, validation_call=False):
        if not (self._token_valid or validation_call):
            logger.debug(f"{self.userid} | Token invalid, skipping request to {path}")
            return None
        headers, method, kwargs, response_timeout  = self.get_headers(params=params, prd_key=prd_key)
        timeout_seconds = response_timeout if not validation_call else response_timeout * 1.5
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            try:
                request_fn = getattr(session, method)
                async with request_fn(f'{self.base_url}{path}', **kwargs) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.info(f"{self.userid} | Non-200 status for {path}: {response.status}")
            except asyncio.TimeoutError:
                logger.info(f"{self.userid} | Timeout fetching {path}")
            except Exception as e:
                if not validation_call:
                    logger.info(f"{self.userid} | Error fetching {path}: {e}")

    async def validate_token(self):
        while not self._stop_event.is_set():
            try:
                prv_status = self._token_valid
                self._token_valid = await self._do_validate_token()
                if self._token_valid:
                    if not prv_status:
                        logger.info(f"{self.userid} | ✅ Token validated")
                    delay = 60
                else:
                    logger.info(f"{self.userid} | ❌ Token expired / not found")
                    await self.r.publish("token_update", self.userid.lower())
                    await asyncio.sleep(15)
                    await self.set_token()
                    delay = 45
            except Exception as e:
                logger.warning(f"{self.userid} | ❌ Token validation error: {e}")
                self._token_valid = False
                delay = 60
            await asyncio.sleep(delay)

    async def _do_validate_token(self):
        return await self.limits(validation_call=True) is not None

    def start_token_validation(self):
        if self._validate_task and not self._validate_task.done():
            return
        self._stop_event = asyncio.Event()  # Reset stop event
        self._validate_task = asyncio.create_task(self.validate_token())

    async def stop_token_validation(self):
        self._stop_event.set()
        if self._validate_task:
            await self._validate_task
        self._validate_task = None  # Clean slate
        self._token_valid = False  # Force revalidation on next start

    async def limits(self, validation_call=False):
        ...  # for validation purpose. define in respective class.

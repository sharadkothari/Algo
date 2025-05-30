from common.my_logger import logger
from common.trading_hours import TradingHours
from common.config import get_redis_client_async
import asyncio
import datetime
import orjson
import pandas as pd
import websockets
import json
from Kite import Kite
from common.config import get_broker_ids
import re
from common.expiry import Expiry


class DataPoller:
    def __init__(self):
        self.brokers = []
        self.ticks = {}
        self.trading_hours = TradingHours()
        self.redis = None
        self.ws_task = None

    async def get_brokers(self):
        brokers = []
        for broker, user_ids in get_broker_ids().items():
            for user in user_ids:
                match broker.lower():
                    case "kite":
                        brokers.append(await Kite.create(user, self.ticks))
        return brokers

    async def start(self):
        self.redis = await get_redis_client_async()
        self.brokers = await self.get_brokers()

        while True:
            if not self.trading_hours.is_open():
                await self.wait_until_market_opens()
                continue

            logger.info("Market open — starting data polling and WebSocket tick receiver.")
            self.ws_task = asyncio.create_task(self.receive_market_ticks())
            try:
                while self.trading_hours.is_open():
                    await self.poll_brokers()
                    await asyncio.sleep(1)
            finally:
                if self.ws_task:
                    self.ws_task.cancel()
                    try:
                        await self.ws_task
                    except asyncio.CancelledError:
                        logger.info("WebSocket task cancelled after market close.")

    async def poll_brokers(self):
        write_ops = []

        # Step 1: Fetch all books in parallel
        fetch_tasks = []
        for broker in self.brokers:
            data_sources = {
                "margin_book": broker.margin_book,
                "position_book": broker.position_book,
            }
            for label, method in data_sources.items():
                fetch_tasks.append((label, broker, method()))

        results = await asyncio.gather(*[coro for _, _, coro in fetch_tasks], return_exceptions=True)

        # Step 2: Prepare data for Redis
        for i, (label, broker, _) in enumerate(fetch_tasks):
            result = results[i]

            if isinstance(result, Exception):
                logger.warning(f"[{broker.name}] Error in {label}: {result}")
                continue

            serialized = self.serialize_data(result)

            write_ops.append((label, f"{broker.name}:{broker.userid}", serialized))

        # Step 3: Single Redis pipeline
        if write_ops:
            async with self.redis.pipeline() as pipe:
                for label, key, value in write_ops:
                    if value and value != "null":  # Prevent writing empty/null values
                        pipe.hset(label, key, value)
                    else:
                        logger.warning(f"[{key}] Skipping Redis update for {label}: value is empty or null")
                await pipe.execute()

            # Second: publish updates outside the pipeline context as pipe doesn't support PUBLISH in asyncio
            for label, key, value in write_ops:
                if value and value != "null":
                    await self.redis.publish(f"{label}_channel", value)

    @staticmethod
    def serialize_data(data):
        if data is None:
            return None
        if isinstance(data, pd.DataFrame):
            if data.empty:
                return None
            return data.to_json(orient="records")  # Keep this as string
        else:
            serialized = orjson.dumps(data).decode()
            if serialized == "null":
                return None
            return serialized

    async def wait_until_market_opens(self):
        wait_time = self.trading_hours.time_until_next_open().total_seconds()
        next_open = datetime.datetime.now() + datetime.timedelta(seconds=wait_time)
        logger.info(f"Market closed. Sleeping until {next_open:%d-%b-%Y %H:%M}")
        await asyncio.sleep(wait_time)

    async def receive_market_ticks(self):
        uri = "ws://e7270:5009/ws/"  # WebSocket URL for quotes
        while True:
            try:
                async with websockets.connect(uri) as websocket:
                    while True:
                        message = await websocket.recv()
                        self.process_ws_message(message)
            except Exception as e:
                logger.warning(f"[WebSocket] Reconnect due to: {e}")
                await asyncio.sleep(5)

    def process_ws_message(self, message):
        tick_updates = json.loads(message)
        for symbol, tick_data in tick_updates.items():
            if symbol not in self.ticks:
                self.ticks[symbol] = {}
                exchange = symbol[:3]
                if exchange in ("NFO", "BFO") and symbol[-3:].upper() != "FUT":
                    e = Expiry({"NFO": "NN", "BFO": "SX"}[exchange])
                    dd = e.get_derivative_data()
                    match = re.match(r"^([A-Z]+)(\d.{4})(.*)(..)$", symbol[4:])
                    # symbol_part = match.group(1)  # String till first digit
                    exp_str = match.group(2)  # First digit + next 4 characters
                    strike = match.group(3)  # Balance characters excluding last two
                    opt_type = match.group(4)  # Last two characters
                    self.ticks[symbol].update({
                        'underlying': f'{dd["exchange"]}:{dd["underlying"]}',
                        'expiry_date': e.expand_exp_str(exp_str),
                        'strike': int(strike),
                        'opt_type': opt_type,
                    })
            self.ticks[symbol].update({
                'last_price': tick_data['last_price'],
                'timestamp': datetime.datetime.fromisoformat(tick_data['exchange_timestamp']),
                'tick': tick_data,
            })

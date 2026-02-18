from common.my_logger import logger
from common_library.trading.trading_hours import TradingHours
from common.config import get_redis_client_v2
import asyncio
import datetime
import pandas as pd
import websockets
import json
from kite import Kite
from shoonya import Shoonya
from neo import Neo
from common.config import get_broker_ids, url_ws
import re
from common.expiry import Expiry
import logging

logger.setLevel(logging.INFO)


class DataPoller:
    BOOK_LABELS = {
        "margin_book": "margin_book",
        "position_book": "position_book"
    }

    def __init__(self):
        self.brokers = []
        self.ticks = {}
        self.trading_hours = TradingHours(start_buffer=300)
        self.redis = None
        self.ws_task = None
        self.test_outside_hours = False

    async def get_brokers(self):
        brokers = []
        broker_obj = {
            'kite': Kite,
            'shoonya': Shoonya,
            'neo': Neo
        }
        for broker, user_ids in get_broker_ids().items():
            broker = broker.lower()
            for user in user_ids:
                if broker in broker_obj:
                    brokers.append(await broker_obj[broker].create(user, self.ticks))
        return brokers

    async def start(self):

        while True:

            if not (self.trading_hours.is_open() or self.test_outside_hours):
                await self.wait_until_market_opens()
                continue

            self.redis = await get_redis_client_v2(asyncio=True, port_ix=0)
            self.brokers = await self.get_brokers()

            logger.info("📈✅ Market open — starting data polling and WebSocket tick receiver.")
            self.ws_task = asyncio.create_task(self.receive_market_ticks())

            await asyncio.sleep(5)

            for broker in self.brokers:
                broker.start_token_validation()
                await self.redis.delete(f"position_book_stream:{broker.name}:{broker.userid}")
            await self.redis.delete("position_book_stream:ALL")

            for label in self.BOOK_LABELS:
                await self.redis.delete(label)
                await self.redis.delete(f"{label}_stream")

            try:
                while self.trading_hours.is_open() or self.test_outside_hours:
                    await self.poll_brokers()
                    await asyncio.sleep(1)
            finally:
                if self.ws_task:
                    self.ws_task.cancel()
                    try:
                        await self.ws_task
                    except asyncio.CancelledError:
                        logger.info("WebSocket task cancelled after market close.")

                for broker in self.brokers:
                    await broker.stop_token_validation()


    async def poll_brokers(self):
        write_ops = []

        # Step 1: Fetch all books in parallel
        fetch_tasks = []
        for broker in self.brokers:
            data_sources = {
                "margin_book": broker.margin_book,
                "position_book": broker.position_book,
            }
            for label, attr in self.BOOK_LABELS.items():
                method = getattr(broker, attr)
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
                        logger.debug(f"[{key}] Skipping Redis update for {label}: value is empty or null")
                        ...
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
            serialized = json.dumps(data)
            if serialized == "null":
                return None
            return serialized

    async def wait_until_market_opens(self):
        logger.info(f"📉⛔ Market closed. Sleeping in short bursts until "
                    f"{(datetime.datetime.now() + self.trading_hours.time_until_next_open()):%d-%b-%Y %H:%M}")

        while not self.trading_hours.is_open():
            remaining = self.trading_hours.time_until_next_open().total_seconds()
            sleep_duration = min(5 * 60, max(remaining, 0))
            await asyncio.sleep(sleep_duration)

    async def receive_market_ticks(self):
        uri = url_ws  # WebSocket URL for quotes
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
        msg = json.loads(message)
        msg_type = msg.get("type")
        data = msg.get("data")

        if msg_type == "tick":
            self.process_tick_data(data)

    def process_tick_data(self, tick_updates):
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

    async def shutdown(self):
        logger.info("Shutting down DataPoller...")
        if self.ws_task:
            self.ws_task.cancel()
            try:
                await self.ws_task
            except asyncio.CancelledError:
                logger.info("WebSocket task cancelled on shutdown.")

        for broker in self.brokers:
            try:
                await broker.stop_token_validation()
            except Exception as e:
                logger.warning(f"Error during broker shutdown: {e}")

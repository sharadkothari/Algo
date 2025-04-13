# simulator.py
import asyncio
import json
import random
import time
from common.config import get_redis_client_async

SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "NIFTY 50"]


async def push_ticks():
    redis_client = await get_redis_client_async()
    while True:
        tick = {
            sym: {
                "last_price": round(random.uniform(1000, 3000), 2),
                "volume": random.randint(100, 1000),
                "exchange_timestamp": time.time()
            }
            for sym in SYMBOLS
        }
        await redis_client.publish("test_ticks", json.dumps(tick))
        await asyncio.sleep(1)


asyncio.run(push_ticks())

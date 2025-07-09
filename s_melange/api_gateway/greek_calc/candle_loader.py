import asyncio
import json
import datetime as dt
from common.config import get_redis_client_v2
from common.expiry import Expiry

async def fetch_latest_candle(redis_client, key):
    raw_candles = await redis_client.zrange(key, -1, -1)
    if not raw_candles:
        return key, None
    candle = json.loads(raw_candles[0])
    return key, candle

async def load_latest_candles_async(underlying="NN", date=dt.date.today()):
    ex = Expiry(underlying)
    redis_client = await get_redis_client_v2(asyncio=True, port_ix=0)

    exch = ex.get_derivative_exchange()
    exp_str = ex.get_exp_str(date)
    keys = await redis_client.keys(f"candles{date:%Y%m%d}:{exch}:{exp_str}d*")

    tasks = [fetch_latest_candle(redis_client, key) for key in keys]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    latest_candles = {}
    for result in results:
        if isinstance(result, Exception):
            continue
        key, candle = result
        if candle:
            latest_candles[key] = candle

    await redis_client.aclose()
    return latest_candles

# Run this from an async-capable environment
if __name__ == '__main__':
    import asyncio
    candles = asyncio.run(load_latest_candles_async())
    print("Total candles:", len(candles))

import asyncio
from kite import Kite
from shoonya import Shoonya
from neo import Neo
from common.config import get_redis_client_async

async def main():
    r = await get_redis_client_async()
    tick = await r.hgetall("tick:20250711")
    broker = await Kite.create("ym3006", tick)
    #broker = await Shoonya.create("fa97273", tick)
    #broker = await Neo.create("ylcgn", tick)
    #await asyncio.sleep(5)
    #broker.start_token_validation()
    #print(await broker.position_book())
    print(await broker.positions())
    #await broker.stop_token_validation()


if __name__ == "__main__":
    asyncio.run(main())

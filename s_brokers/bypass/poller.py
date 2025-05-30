import asyncio
from data_poller import DataPoller
from Kite import Kite
from common.config import get_broker_ids


async def main():
    db = DataPoller()
    await db.start()


if __name__ == "__main__":
    asyncio.run(main())

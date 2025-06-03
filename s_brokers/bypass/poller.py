import asyncio
from data_poller import DataPoller

async def main():
    db = DataPoller()
    try:
        await db.start()
    except asyncio.CancelledError:
        print("Shutting down... CancelledError caught.")
        await db.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutdown requested by user (KeyboardInterrupt).")

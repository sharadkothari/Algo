import asyncio
from data_poller import DataPoller
from position_book_stream import PositionBookStreamer

async def main():
    db = DataPoller()
    streamer = PositionBookStreamer()
    try:
        await asyncio.gather(
            db.start(),
            streamer.start()
        )
    except asyncio.CancelledError:
        print("Shutting down... CancelledError caught.")
        await db.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutdown requested by user (KeyboardInterrupt).")

import asyncio
import websockets
import json # Ticks are often sent as JSON
import datetime # For timestamping or time-based processing
from common.config import url_ws

async def receive_market_ticks():
    # "ws://100.123.122.115:5009/ws/"
    #
    uri = url_ws # Your WebSocket URL for quotes
    ticks = {}

    while True: # Loop indefinitely to maintain connection and auto-reconnect
        try:
            async with websockets.connect(uri) as websocket:
                while True: # Loop to continuously receive messages
                    try:
                        message = await websocket.recv()
                        message = json.loads(message)
                        if message["type"] == "tick":
                            print(message["data"].get('NSE:NIFTY 50'))
                    except Exception as e:
                        print(f"An error occurred while receiving a message: {e}. Attempting to reconnect...")
                        break # Exit inner loop to attempt re-connection
        except Exception as e:
            print(f"An unexpected error occurred during connection attempt: {e}")
        print("Waiting for 5 seconds before attempting to reconnect...")
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(receive_market_ticks())
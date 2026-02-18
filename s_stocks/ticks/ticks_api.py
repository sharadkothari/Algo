from fastapi import FastAPI
from contextlib import asynccontextmanager
from ticks import KiteSocket
from fastapi.middleware.cors import CORSMiddleware

# Global placeholder
socket_instance:KiteSocket | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    global socket_instance
    # Initialize the socket logic on API startup
    socket_instance = KiteSocket(client_id="YM3006")
    yield
    # Cleanup on shutdown
    if socket_instance:
        socket_instance.stop()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, # type: ignore
    allow_origins=["*"],  # restrict here
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def get_latest_prices():
    if not socket_instance:
        return {"error": "Socket not initialized"}

    return socket_instance.ticks


@app.get("/{symbol}")
async def get_single_symbol(symbol: str):
    """Access a specific symbol directly: e.g., /ticks/NSE:INFY"""
    if not socket_instance:
        return {"error": "Socket not initialized"}

    tick = socket_instance.ticks.get(symbol)
    if not tick:
        return {"error": "Symbol not found or no tick received yet"}
    return tick

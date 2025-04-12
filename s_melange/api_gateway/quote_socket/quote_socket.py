from fastapi import WebSocket, WebSocketDisconnect, APIRouter
import asyncio
from common.config import get_redis_client_async
from common.my_logger import logger

active_clients = set()
redis_task = None  # task handle

router = APIRouter(prefix="/ws")


@router.get("/check")
def ws_check():
    return {"message": "checked"}


@router.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    global redis_task

    await websocket.accept()
    active_clients.add(websocket)

    # Start listener if this is the first client
    if redis_task is None or redis_task.done():
        redis_task = asyncio.create_task(redis_listener())

    try:
        while True:
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        active_clients.discard(websocket)

        # Stop listener if no clients are connected
        if not active_clients and redis_task and not redis_task.done():
            redis_task.cancel()
            try:
                await redis_task
            except asyncio.CancelledError:
                logger.info("Redis listener cancelled cleanly")


async def redis_listener():
    redis_client = await get_redis_client_async()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("test_ticks")

    try:
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                for ws in list(active_clients):
                    try:
                        await ws.send_text(msg["data"])
                    except:
                        active_clients.remove(ws)
    except asyncio.CancelledError:
        logger.info("Listener cancelled")
    finally:
        await pubsub.unsubscribe("test_ticks")
        await redis_client.close()

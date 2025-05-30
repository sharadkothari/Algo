from fastapi import WebSocket, WebSocketDisconnect, APIRouter
import asyncio
from common.config import get_redis_client_async
from common.my_logger import logger
from asyncio.exceptions import CancelledError
from redis.asyncio.connection import ConnectionError as RedisConnectionError
from redis.exceptions import ConnectionError as SyncRedisConnectionError

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
    while True:
        try:
            pubsub = redis_client.pubsub()
            await pubsub.subscribe("tick_channel")

            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    for ws in list(active_clients):
                        try:
                            await ws.send_text(msg["data"])
                        except Exception:
                            active_clients.discard(ws)

        except (RedisConnectionError, SyncRedisConnectionError, asyncio.IncompleteReadError) as e:
            logger.error(f"🔁 Redis connection error, retrying in 2s: {e}")
            await asyncio.sleep(2)
        except CancelledError:
            logger.info("🔕 Redis listener cancelled.")
            break
        except Exception as e:
            logger.exception(f"❌ Unexpected error in redis_listener: {e}")
            await asyncio.sleep(2)
        finally:
            try:
                await pubsub.unsubscribe("tick_channel")
            except Exception:
                pass
            try:
                await redis_client.close()
            except Exception:
                pass


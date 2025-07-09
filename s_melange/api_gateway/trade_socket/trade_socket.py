from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json
from common.config import get_redis_client_async
from common.my_logger import logger
from redis.asyncio.connection import ConnectionError as RedisConnectionError
from redis.exceptions import ConnectionError as SyncRedisConnectionError
from asyncio.exceptions import CancelledError

router = APIRouter(prefix="/ws")

channel_to_type = {
    "tick_channel": "tick",
    "position_book_channel": "position_book",
    "margin_book_channel": "margin_book",
}

class ClientStream:
    def __init__(self, websocket: WebSocket):
        self.ws = websocket
        self.queues = {
            "tick": asyncio.Queue(maxsize=10),
            "position_book": asyncio.Queue(maxsize=1),
            "margin_book": asyncio.Queue(maxsize=1),
        }

active_clients: set[ClientStream] = set()
redis_task = None  # Task handle for Redis listener


@router.get("/check")
def ws_check():
    return {"message": "checked"}


@router.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    global redis_task

    await websocket.accept()
    client = ClientStream(websocket)
    active_clients.add(client)

    # Start Redis listener if not already running
    if redis_task is None or redis_task.done():
        redis_task = asyncio.create_task(redis_listener())

    sender_task = asyncio.create_task(send_to_client(client))

    try:
        await sender_task  # No idle loop needed here
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    finally:
        active_clients.discard(client)
        sender_task.cancel()
        try:
            await sender_task
        except asyncio.CancelledError:
            pass

        if not active_clients and redis_task and not redis_task.done():
            redis_task.cancel()
            try:
                await redis_task
            except asyncio.CancelledError:
                logger.info("Redis listener cancelled cleanly")


async def redis_listener():
    redis_client = await get_redis_client_async()
    try:
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(*channel_to_type.keys())

        async for msg in pubsub.listen():
            if msg["type"] != "message":
                continue

            try:
                msg_type = channel_to_type.get(msg["channel"])
                data = json.loads(msg["data"])
                wrapped_msg = {"type": msg_type, "data": data}
            except Exception as parse_error:
                logger.warning(f"Skipping malformed message: {parse_error}")
                continue

            for client in list(active_clients):
                queue = client.queues.get(msg_type)
                if not queue:
                    continue
                try:
                    if queue.full():
                        _ = queue.get_nowait()  # drop oldest
                    queue.put_nowait(wrapped_msg)
                except Exception as queue_error:
                    logger.warning(f"Queue error: {queue_error}")
                    active_clients.discard(client)

    except (RedisConnectionError, SyncRedisConnectionError, asyncio.IncompleteReadError) as e:
        logger.error(f"🔁 Redis connection error, retrying in 2s: {e}")
        await asyncio.sleep(2)
    except CancelledError:
        logger.info("🔕 Redis listener cancelled.")
    except Exception as e:
        logger.exception(f"❌ Unexpected error in redis_listener: {e}")
        await asyncio.sleep(2)
    finally:
        try:
            await pubsub.unsubscribe(*channel_to_type.keys())
        except Exception:
            pass
        try:
            await redis_client.close()
        except Exception:
            pass


async def send_to_client(client: ClientStream):
    try:
        while True:
            tasks = [asyncio.create_task(queue.get()) for queue in client.queues.values()]
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

            for task in done:
                try:
                    msg = task.result()
                    await client.ws.send_json(msg)
                except Exception as e:
                    # logger.debug(f"Client send failed: {type(e).__name__} - {e}")
                    return  # exit on failure

    except asyncio.CancelledError:
        pass  # graceful shutdown


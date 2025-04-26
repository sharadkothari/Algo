from fastapi import FastAPI, Request, HTTPException, APIRouter
from fastapi.responses import PlainTextResponse
import httpx
import json
import datetime
from common.config import data_dir, get_redis_client_async
from common.my_logger import logger
from .telegram_handler import TelegramHandlerManager
from redis.asyncio import Redis

app = FastAPI()
router = APIRouter(prefix="/telegram")

with open(data_dir / 'telegram.json', 'r') as f:
    telegram_data = json.loads(f.read())

TOKEN = telegram_data['token']
NGROK_URL = telegram_data['ngrok_url']
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TOKEN}"

# Redis and Handler setup
handler_manager: TelegramHandlerManager | None = None
redis_client: Redis | None = None


async def init_handler_manager():
    global handler_manager, redis_client
    redis_client = await get_redis_client_async()
    handler_manager = TelegramHandlerManager(redis_client=redis_client, api_url=TELEGRAM_API_URL)


@router.on_event("startup")
async def on_startup():
    async with httpx.AsyncClient() as client:
        payload = {
            "url": f"{NGROK_URL}/telegram/webhook",
            "allowed_updates": ["message", "channel_post", "callback_query"]
        }
        try:
            logger.info(f"Setting webhook to {NGROK_URL}/webhook...")
            response = await client.post(f"{TELEGRAM_API_URL}/setWebhook", json=payload)
            logger.info(f"Webhook Setup Response: {response.json()}")
        except httpx.RequestError as e:
            logger.error(f"Webhook setup failed: {e}")
    await init_handler_manager()


@router.get("/status")
async def webhook_status():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{TELEGRAM_API_URL}/getWebhookInfo")
        return response.json()


@router.post("/send")
async def send(data: dict):
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API_URL}/sendMessage", json=data)
    return {"ok": True}


@router.post("/webhook")
async def webhook(req: Request):
    try:
        data = await req.json()
        if not data:
            raise HTTPException(status_code=400, detail="No data received")

        await redis_client.xadd("telegram_dump", {
            "time": datetime.datetime.now().isoformat(timespec="seconds"),
            "data": json.dumps(data)
        }, maxlen=1000)

        await handler_manager.store_message(data)
        return {"status": "ok"}

    except Exception as e:
        logger.exception("🚨 Exception in webhook handler")
        raise HTTPException(status_code=400, detail=f"Webhook error: {e}")


@router.get("/ngrok_url")
async def ngrok_url():
    return NGROK_URL


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/streams/m3u", response_class=PlainTextResponse)
async def get_m3u():
    with open(data_dir / 'M3U8.json', 'r') as file:
        m3u8_links = json.loads(file.read())

    m3u_content = "#EXTM3U\n"
    for channel_name, stream_url in m3u8_links.items():
        m3u_content += f"#EXTINF:-1,{channel_name}\n{stream_url}\n"

    return m3u_content

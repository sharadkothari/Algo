from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from trade_socket.trade_socket import router as ws_router
from trade_socket.trade_socket import redis_listener
from test.test import router as test_router
from docker_db.docker_db import router as docker_db_router
from health.health import router as health_router
from telegram.telegram import router as telegram_router, on_startup as telegram_startup
from bypass_data.bypass_data import router as bypass_data_router
from alerts.alerts_ui import router as alerts_ui_router
from alerts.alerts_api import router as alerts_api_router
from common.my_logger import logger
import asyncio
from common.base_service import BaseService
from common.utils import get_ngrok_url
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware

redis_task = None
base_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_task, base_service
    print("🚀 Startup", flush=True)

    # 1. Start Redis WebSocket listener
    try:
        redis_task = asyncio.create_task(redis_listener())
    except Exception as e:
        logger.error(f"Failed to start Redis listener: {e}")

    # 2. Start any custom startup tasks
    get_ngrok_url()
    await telegram_startup()

    # 3. Now start BaseService (so Telegram bot is ready to send)
    base_service = BaseService(app_name=Path(__file__).stem)

    yield  # ----> Application runs here

    print("🛑 Shutdown", flush=True)

    # Cleanly cancel Redis task
    if redis_task and not redis_task.done():
        redis_task.cancel()
        try:
            await redis_task
        except asyncio.CancelledError:
            logger.info("Redis listener cancelled cleanly")

    if base_service:
        base_service.on_stop()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, # type: ignore
    allow_origins=["*"],  # restrict here
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(HTTPException)
async def common_http_exception_handler(request: Request, exc: HTTPException):
    _ = request
    logger.error(f"Unhandled error: {repr(exc)}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": f"Handled by common handler: {exc.detail}"},
    )


@app.get("/")
def read_root():
    return {"message": "Hello, World!"}


@app.get("/hello")
def read_root():
    return {"message": "Hello!!"}


app.include_router(ws_router)
app.include_router(test_router)
app.include_router(docker_db_router)
app.include_router(health_router)
app.include_router(telegram_router)
app.include_router(bypass_data_router)
app.include_router(alerts_ui_router)
app.include_router(alerts_api_router)

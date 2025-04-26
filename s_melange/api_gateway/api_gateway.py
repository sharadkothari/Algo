from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from quote_socket.quote_socket import router as ws_router
from test.test import router as test_router
from docker_db.docker_db import router as docker_db_router
from health.health import router as health_router
from telegram.telegram import router as telegram_router, on_startup as telegram_startup
from common.my_logger import logger

@asynccontextmanager
async def lifespan(_app: FastAPI):
    _ = _app
    print("🚀 Startup", flush=True)
    await telegram_startup()
    yield
    print("🛑 Shutdown", flush=True)


app = FastAPI(lifespan=lifespan)


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
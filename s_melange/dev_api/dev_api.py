from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from common.my_logger import logger
from common.base_service import BaseService
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from alerts_spread.alerts_spread import router as alerts_spread_router
from algo_eq.algo_eq import  router as algo_eq_router
import datetime as dt

redis_task = None
base_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global base_service
    print(f">>> Lifespan startup at {dt.datetime.now().isoformat()}")
    logger.info("🚀 Starting Development Server")

    base_service = BaseService(app_name=Path(__file__).stem)

    yield  # ----> Application runs here

    logger.info("🛑 Shutdown")

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
    return {"message": "Hello, Development World!"}


@app.get("/hello")
def read_root():
    return {"message": "Hello Development!!"}

app.include_router(alerts_spread_router)
app.include_router(algo_eq_router)
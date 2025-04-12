from fastapi import FastAPI
from contextlib import asynccontextmanager
from quote_socket.quote_socket import router as ws_router
from test.test import router as test_router

@asynccontextmanager
async def lifespan(_app: FastAPI):
    _ = _app
    print("🚀 Startup", flush=True)
    yield
    print("🛑 Shutdown", flush=True)


app = FastAPI(lifespan=lifespan)


@app.get("/")
def read_root():
    return {"message": "Hello, World!"}


@app.get("/hello")
def read_root():
    return {"message": "Hello!!"}


app.include_router(ws_router)
app.include_router(test_router)
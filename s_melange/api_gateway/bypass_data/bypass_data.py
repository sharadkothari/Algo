from fastapi import APIRouter
from fastapi.responses import JSONResponse
from common.config import get_redis_client
import redis

router = APIRouter(prefix="/bpd")
r: redis = get_redis_client()


@router.get("/brokers")
async def get_brokers():
    return list(r.hgetall("position_book").keys()) + ["ALL"]


@router.get("/mtm-data")
async def get_mtm_data(broker: str):
    entries = r.xrange("position_book_stream")
    data = []
    for _, fields in entries:
        if fields.get("Broker") == broker:
            data.append({
                "timestamp": fields["timestamp"],
                "MTM": float(fields["MTM"])
            })

    if data:
        data.sort(key=lambda x: x["timestamp"])

    return data

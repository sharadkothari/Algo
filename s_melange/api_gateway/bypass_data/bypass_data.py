from fastapi import APIRouter
from fastapi.responses import JSONResponse
from common.config import get_redis_client
import redis

router = APIRouter(prefix="/bpd")
r: redis = get_redis_client()


def bump_id(last_id):
    try:
        ts, seq = last_id.split("-")
        return f"{ts}-{int(seq) + 1}"
    except Exception:
        return "0-1"


@router.get("/brokers")
async def get_brokers():
    return list(r.hgetall("position_book").keys()) + ["ALL"]


@router.get("/mtm-data")
async def get_mtm_data(broker: str, last_id: str = "0"):
    data = []

    entries = r.xrange(f"position_book_stream:{broker}", min=bump_id(last_id), max="+")

    for entry_id, fields in entries:
        data.append({
            "timestamp": fields["timestamp"],
            "MTM": float(fields["MTM"])
        })

    latest_id = entries[-1][0] if entries else last_id
    return {"data": data, "last_id": latest_id}

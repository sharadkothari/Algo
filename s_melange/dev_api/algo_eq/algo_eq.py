from fastapi import APIRouter, Response
from common.config import get_redis_client_v2
import json
import gzip

router = APIRouter(prefix="/algo-eq", tags=["algo-eq"])
r = get_redis_client_v2(decode=False)
r_decode =  get_redis_client_v2(decode=True)
redis_suffix = r_decode.get('algo-eq:suffix')

def bump_id(last_id):
    try:
        ts, seq = last_id.split("-")
        return f"{ts}-{int(seq) + 1}"
    except Exception:
        return "0-1"

@router.get("/orderbook")
def get_orderbook():
    compressed =r.get(f"algo-eq:orderbook:{redis_suffix}")
    return Response(content=compressed, media_type="application/json", headers={"Content-Encoding": "gzip"})

@router.get("/symbolstate")
def get_symbolstate():
    compressed = r.get(f"algo-eq:symbolstate:{redis_suffix}")
    return Response(content=compressed, media_type="application/json", headers={"Content-Encoding": "gzip"})

@router.get("/daystate")
def get_symbolstate():
    compressed = r.get(f"algo-eq:daystate:{redis_suffix}")
    return Response(content=compressed, media_type="application/json", headers={"Content-Encoding": "gzip"})

@router.get("/overallmtm")
def get_mtm_data(last_id: str = "0"):
    data = []
    entries = r_decode.xrange(f"algo-eq:pos_out:{redis_suffix}", min=bump_id(last_id), max="+")

    for entry_id, fields in entries:
        data.append({
            "timestamp": fields["ts"],
            "MTM": float(fields["mtm"])
        })
    latest_id = entries[-1][0] if entries else last_id
    return {"data": data, "last_id": latest_id}


@router.get("/pos-data")
def get_mtm_data(last_id: str = "0"):
    entries = r_decode.xrange(f"algo-eq:pos_out:{redis_suffix}", min=bump_id(last_id), max="+")
    latest_id = entries[-1][0] if entries else last_id
    return {"data": entries, "last_id": latest_id}

@router.get("/suffix/refresh")
def refresh_suffix():
    global redis_suffix
    redis_suffix = r_decode.get("algo-eq:suffix")
    return {"ok": True, "suffix": redis_suffix}


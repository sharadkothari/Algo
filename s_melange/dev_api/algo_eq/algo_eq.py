from fastapi import APIRouter, Response
from common.config import get_redis_client_v2
import json
import gzip

router = APIRouter(prefix="/algo-eq", tags=["algo-eq"])
r = get_redis_client_v2(decode=False)

@router.get("/orderbook")
def get_orderbook():
    compressed =r.get("algo-eq:orderbook:latest")
    return Response(content=compressed, media_type="application/json", headers={"Content-Encoding": "gzip"})

@router.get("/symbolstate")
def get_symbolstate():
    compressed = r.get("algo-eq:symbolstate:latest")
    return Response(content=compressed, media_type="application/json", headers={"Content-Encoding": "gzip"})

@router.get("/overallmtm")
def get_overallmtm():
    return r.json().get("algo-eq:overall_mtm:latest")

@router.get("/symbolmtm")
def get_symbolmtm():
    return r.json().get("algo-eq:symbol_mtm:latest")


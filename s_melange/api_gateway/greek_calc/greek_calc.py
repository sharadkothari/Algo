from fastapi import FastAPI, Query
from candle_loader import load_latest_candles
from delta_engine import compute_deltas
from config import LOT_SIZE
from pydantic import BaseModel

app = FastAPI()
session_deltas = {}

@app.post("/deltas/refresh")
def refresh_deltas(spot: float, expiry_days: int):
    candles = load_latest_candles()
    deltas = compute_deltas(candles, spot, expiry_days, option_type_hint=None)
    global session_deltas
    session_deltas = deltas
    return {"message": "Deltas refreshed", "count": len(deltas)}

class CalcRequest(BaseModel):
    positional_delta: float
    strike_offset: int
    option_type: str  # 'CE' or 'PE'

@app.get("/calc")
def calculate(request: CalcRequest):
    if not session_deltas:
        return {"error": "No delta data — please refresh first."}

    keys = list(session_deltas.keys())
    target_keys = [k for k in keys if k.endswith(f"d{request.strike_offset}{request.option_type}")]

    if not target_keys:
        return {"error": "No matching strike found."}

    data = session_deltas[target_keys[0]]
    per_lot_delta = abs(data["delta"] * LOT_SIZE)
    lots_needed = abs(request.positional_delta) / per_lot_delta if per_lot_delta else 0

    # Decide direction
    if request.positional_delta < 0:
        action = "Short PE" if request.option_type == "PE" else "Long CE"
    else:
        action = "Short CE" if request.option_type == "CE" else "Long PE"

    return {
        "strike": data["strike"],
        "ltp": data["ltp"],
        "option_delta": data["delta"],
        "per_lot_delta": per_lot_delta,
        "lots_needed": round(lots_needed, 2),
        "action": action
    }

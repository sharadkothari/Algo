from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from common.trading_hours import TradingHours
router = APIRouter(prefix="/alerts1", tags=["alerts-ui"])
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR))


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("alerts.html", {"request": request})


@router.get("/play-alert")
def play_alert():
    return FileResponse(BASE_DIR / "alert.mp3", media_type='audio/mp3')

import httpx
from fastapi import APIRouter
import requests
import datetime as dt
import psutil
import platform

router = APIRouter(prefix="/health")
SERVICES = {
    "u530": ["health", "kws_status"],
    "e6330": ["health", "kws_status"],
    "e6330-2": ["health", "kws_status"]
}


def check_server_path(server, path):
    try:
        return requests.get(f"http://{server}/{path}", timeout=2).json()
    except:
        return {"status": "down"}

@router.get("/")
def all_status():
    status_report = {}

    for server, endpoints in SERVICES.items():
        status_report[server] = {}
        for endpoint in endpoints:
            result = check_server_path(server, endpoint)
            status_report[server][endpoint] = result.get("status", "unknown")
    return status_report

@router.get("/internet-status")
async def internet_status():
    try:
        # Check internet connectivity
        async with httpx.AsyncClient(timeout=2) as client:
            await client.get("https://1.1.1.1")

        return {
            "status": "ok",
            "timestamp": dt.datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "status": "fail",
            "error": str(e),
            "timestamp": dt.datetime.utcnow().isoformat(),
        }

@router.get("/stats")
def get_stats():
    battery=psutil.sensors_battery()
    if battery is not None:
        plugged = '⚡' if battery.power_plugged else ''
        battery_stat = [f'{battery.percent:.0f}% {plugged}']
    else:
        battery_stat = ["NA"]
    return {
        "hostname": platform.node(),
        "cpu": psutil.cpu_percent(),
        "memory": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage('/').percent,
        "battery": battery_stat,
        "time": dt.datetime.now().strftime("%H:%M:%S")
    }
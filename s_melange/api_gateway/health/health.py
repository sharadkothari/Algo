from fastapi import APIRouter
import requests

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

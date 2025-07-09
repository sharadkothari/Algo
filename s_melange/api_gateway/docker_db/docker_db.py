from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from .docker_handler import DockerHandler

router = APIRouter(prefix="/docker_db")
dh = DockerHandler()


@router.get('/services')
def get_services():
    result, status = dh.get_services()
    return JSONResponse(content=result, status_code=status)


@router.post('/start/{container_id}')
def start_container(container_id: str):
    result, status = dh.start_container(container_id)
    return JSONResponse(content=result, status_code=status)


@router.post('/stop/{container_id}')
def stop_container(container_id: str):
    result, status = dh.stop_container(container_id)
    return JSONResponse(content=result, status_code=status)


@router.post('/restart/{container_id}')
def restart_container(container_id: str):
    result, status = dh.restart_container(container_id)
    return JSONResponse(content=result, status_code=status)


@router.get("/logs/{service_name}", response_class=HTMLResponse)
async def fetch_logs(service_name: str):
    result = dh.get_log(service_name)

    if "error" in result:
        raise HTTPException(status_code=result.get(1, 500), detail=result["error"])
    if type(result) is dict:
        return result.get("logs")
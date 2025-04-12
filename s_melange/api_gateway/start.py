import uvicorn
from common.uvicorn_config import *

if __name__ == "__main__":
    uvicorn.run(
        "api_gateway:app",
        port=5009,
        host=host,
        reload=reload,
        workers=workers,
        log_level=log_level,
        loop = loop,
    )

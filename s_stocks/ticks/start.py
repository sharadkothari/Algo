import uvicorn
from common.uvicorn_config import *

if __name__ == "__main__":
    uvicorn.run(
        "ticks_api:app",
        port=5011,
        host=host,
        reload=reload,
        workers=workers,
        log_level=log_level,
        loop = loop,
    )

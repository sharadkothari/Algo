import uvicorn
from common.uvicorn_config import *

if __name__ == "__main__":
    uvicorn.run(
        "dev_api:app",
        port=5010,
        host=host,
        reload=reload,
        workers=workers,
        log_level=log_level,
        loop = loop,
    )
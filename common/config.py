from pathlib import Path
import redis
import os

server_url = 'http://100.123.122.115'
redis_host = '100.123.122.115'
redis_port = 6379
redis_db = 0
redis_hash = "tick"

base_dir = Path(__file__).resolve().parent.parent
base_dir_prv = Path(__file__).resolve().parent.parent.parent.parent / 'OneDrive/Algo'

data_dir = base_dir / 'common/data/'

bhavcopy_dir = base_dir_prv / 'bhavcopy'

if os.getenv("DOCKERIZED"):
    parquet_dir = Path("/app/parquet")  # Docker path
    url_docker_db = "http://nginx/docker_db"
else:
    parquet_dir = base_dir_prv / 'screener/parquet'
    url_docker_db = f"{server_url}/docker_db"


def get_redis_client():
    redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
    redis_client.config_set('notify-keyspace-events', 'Khg')
    return redis_client


if __name__ == "__main__":
    _redis_client = get_redis_client()

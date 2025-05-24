from pathlib import Path
import redis
import os
import yaml
import platform

server_url = 'http://100.123.122.115'
redis_host = '100.123.122.115'
redis_port = 6379
redis_db = 0
redis_hash = "tick"

base_dir = Path(__file__).resolve().parent.parent
base_dir_prv = Path(__file__).resolve().parent.parent.parent.parent / 'OneDrive/Algo'

data_dir = base_dir / 'common/data/'

bhavcopy_dir = base_dir_prv / 'bhavcopy'

if Path('/.dockerenv').exists():
    parquet_dir = Path("/app/parquet")  # Docker path
    url_docker_db = "http://nginx/api/docker_db"
else:
    parquet_dir = base_dir_prv / 'screener/parquet'
    url_docker_db = f"{server_url}/api/docker_db"


def get_redis_client():
    redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
    redis_client.config_set('notify-keyspace-events', 'Khg')
    return redis_client


async def get_redis_client_async():
    redis_client = redis.asyncio.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
    await redis_client.config_set('notify-keyspace-events', 'Khg')
    return redis_client


def get_browser_profiles():
    with open(base_dir / "common/config_node.yaml") as f:
        cfg_node = yaml.safe_load(f)
    return cfg_node[platform.node()]['profiles']


def get_broker_ids():
    with open(base_dir / "common/config_brokers.yaml") as f:
        cfg_brokers = yaml.safe_load(f)
    return cfg_brokers['id']


if __name__ == "__main__":
    print(get_browser_profiles())

from flask import jsonify
from common.config import redis_host, redis_port, redis_db
import redis
import datetime
import requests
import os
import docker


def list_routes(app):
    """Returns all available routes in a microservice"""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            "route": str(rule),
            "methods": list(rule.methods - {"HEAD", "OPTIONS"})  # Remove default methods
        })
    return jsonify(routes)


def register_service(module_name, port):
    redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
    redis_client.hset("services", module_name, f"{port}")
    return f"Registered {module_name} at {port}"


class DockerLog:
    def __init__(self):
        self.client = docker.from_env()
        self.tail = 50

    @staticmethod
    def get_container_id():
        try:
            with open("/proc/self/cgroup", "r") as f:
                for line in f:
                    parts = line.strip().split("/")
                    if len(parts) > 2 and parts[-1]:  # Last part contains the container ID
                        return parts[-1]
        except Exception as e:
            print(f"Error retrieving container ID: {e}")
        return None

    def read_docker_log(self):
        if container_id := self.get_container_id():
            try:
                client = docker.from_env()
                container = client.containers.get(container_id)
                logs = container.logs(tail=self.tail)
                return logs.decode('utf-8')
            except Exception as e:
                print(f"Error: {e}")
                return None

# common/utils.py
def greet(name):
    return f"Hello, {name} from shared utils!"

if __name__ == "__main__":
    ...


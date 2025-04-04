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


if __name__ == "__main__":
    ...


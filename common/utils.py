from flask import jsonify
from common.config import redis_host, redis_port, redis_db
import redis
import datetime
import requests
import os
import docker
import base64
from itertools import zip_longest


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


class Encrypt:

    def __init__(self, key1, key2="0000"):
        self.key = ''.join(a + b if b else a for a, b in zip_longest(key1, key2, fillvalue=""))

    def encrypt(self, data: str) -> str:
        extended_key = (self.key * (len(data) // len(self.key) + 1))[:len(data)]
        encrypted_bytes = bytes([ord(d) ^ ord(k) for d, k in zip(data, extended_key)])
        return base64.urlsafe_b64encode(encrypted_bytes).decode()

    def decrypt(self, data: str) -> str:
        encrypted_bytes = base64.urlsafe_b64decode(data.encode())
        extended_key = (self.key * (len(encrypted_bytes) // len(self.key) + 1))[:len(encrypted_bytes)]
        return "".join(chr(e ^ ord(k)) for e, k in zip(encrypted_bytes, extended_key))



if __name__ == "__main__":
    e = Encrypt("YLCGN")
    print(e.encrypt("iGo1ofkqrrKkfKD7oT0aHvsP0uka"))
    print(e.encrypt("Kotak@1"))

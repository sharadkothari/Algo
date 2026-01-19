from flask import jsonify
import redis
import datetime
import requests
import os
import docker
import base64
from itertools import zip_longest
from common.config import server_url, get_redis_client_v2
from common.my_logger import logger

redis_0 =  get_redis_client_v2(port_ix=0)
redis_1 = get_redis_client_v2(port_ix=1)


def get_ngrok_url():
    try:
        response = requests.get(f"{server_url}:4040/api/tunnels", timeout=5)
        data = response.json()
        tunnels = data.get("tunnels", [])
        if tunnels:
            if public_url := tunnels[0].get("public_url"):
                redis_1.set("ngrok_url", public_url)
                logger.info(f"ngrok url is {public_url}")
    except:
        logger.error(f"error getting / storing ngrok url")


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
    redis_0.hset("services", module_name, f"{port}")
    return f"Registered {module_name} at {port}"


class Encrypt:

    def __init__(self, key1, key2="0000"):
        self.key = ''.join(a + b if b else a for a, b in zip_longest(key1, key2, fillvalue=""))

    def encrypt(self, data: str) -> str:
        extended_key = (self.key * (len(data) // len(self.key) + 1))[:len(data)]
        encrypted_bytes = bytes([ord(d) ^ ord(k) for d, k in zip(data, extended_key)])
        return base64.urlsafe_b64encode(encrypted_bytes).decode()

    def decrypt(self, data: str) -> str:
        if data is not None:
            encrypted_bytes = base64.urlsafe_b64decode(data.encode())
            extended_key = (self.key * (len(encrypted_bytes) // len(self.key) + 1))[:len(encrypted_bytes)]
            return "".join(chr(e ^ ord(k)) for e, k in zip(encrypted_bytes, extended_key))
        else:
            return ""


class TimeCalc:
    def __init__(self):
        ...

    @staticmethod
    def next_6am(hour=6):
        now = datetime.datetime.now()
        if now.hour >= hour:
            next_6am = (now + datetime.timedelta(days=1)).replace(hour=hour, minute=0, second=0, microsecond=0)
        else:
            next_6am = now.replace(hour=6, minute=0, second=0, microsecond=0)
        return next_6am


if __name__ == "__main__":
    e = Encrypt("YL6GN")
    print(e.encrypt("cd7b3e73-cdcb-4d5b-b51f-553c6d749653"))
    print(e.encrypt("+919716000025"))
    print(e.encrypt("YL6GN"))
    print(e.encrypt("C2ETBVULDFSPV27OU6U4SJNMUA"))
    print(e.encrypt("691025"))
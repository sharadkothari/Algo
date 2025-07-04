import sys

from kite_token import get_token as get_kite_token
from shoonya_token import get_token as get_shoonya_token
from neo_token import get_token as get_neo_token
from common.config import get_broker_ids
from common.config import get_redis_client_v2
import time


def get_tokens(value):
    time.sleep(1)  # needed for sending the telegram message
    for broker, ids in get_ids_to_process(value).items():
        match broker.lower():
            case 'kite':
                get_kite_token(ids)
            case 'shoonya':
                get_shoonya_token(ids)
            case 'neo':
                get_neo_token(ids)


def get_ids_to_process(value):
    data = get_broker_ids()
    value = value.lower()
    if value == "all":
        return data
    elif value in get_broker_ids():
        return {value: data[value]}
    else:
        broker = next((k for k, v in data.items() if value in v), None)
        return {broker: [value]}


def token_update_worker():
    r = get_redis_client_v2(port_ix=1)
    pubsub = r.pubsub()
    pubsub.subscribe("token_update")

    print("Listening for token update triggers...")
    for message in pubsub.listen():
        if message['type'] == 'message':
            get_tokens(message['data'])


if __name__ == '__main__':
    token_update_worker()

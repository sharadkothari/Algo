from kite_token import get_token as get_kite_token
from shoonya_token import get_token as get_shoonya_token
from neo_token_async import get_token as get_neo_token


def get_all_tokens():
    get_kite_token()
    get_shoonya_token()
    get_neo_token()


if __name__ == '__main__':
    get_all_tokens()

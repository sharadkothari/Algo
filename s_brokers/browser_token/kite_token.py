import browser_cookie_3x
from common_token import CommonToken
import requests


def get_cookie_token(cookie_path):
    cj = browser_cookie_3x.edge(cookie_file=cookie_path, domain_name='kite.zerodha.com')
    return f"enctoken {cj._cookies['kite.zerodha.com']['/']['enctoken'].value}"


def validate_token(token, client):
    headers = {"Authorization": token}
    try:
        url = "https://kite.zerodha.com/oms/user/margins"
        response = requests.get(url, headers=headers, timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        return False


def get_token(client_ids=('ym3006', 'rs5756', 'mim066')):
    CommonToken(client_ids, get_cookie_token, validate_token)


if __name__ == "__main__":
    get_token(['ym3006'])

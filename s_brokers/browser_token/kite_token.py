import browser_cookie_3x
from common_token import CommonToken


def get_cookie_token(cookie_path):
    cj = browser_cookie_3x.edge(cookie_file=cookie_path, domain_name='kite.zerodha.com')
    return f"enctoken {cj._cookies['kite.zerodha.com']['/']['enctoken'].value}"


def get_token(client_ids=('ym3006', 'rs5756', 'mim066')):
    CommonToken(client_ids, get_cookie_token)


if __name__ == "__main__":
    get_token()

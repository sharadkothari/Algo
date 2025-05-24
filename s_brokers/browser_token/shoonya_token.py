import browser_cookie_3x
from common_token import CommonToken


def get_cookie_token(cookie_path):
    cj = browser_cookie_3x.edge(cookie_file=cookie_path, domain_name='trade.shoonya.com')
    return cj._cookies['trade.shoonya.com']['/']['NWC_ID'].value


def get_token(client_ids=('fa97273', 'fa222351')):
    CommonToken(client_ids, get_cookie_token)


if __name__ == "__main__":
    get_token()

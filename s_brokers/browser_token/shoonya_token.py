import browser_cookie_3x
from common_token import CommonToken
import requests
import json
def get_cookie_token(cookie_path):
    cj = browser_cookie_3x.edge(cookie_file=cookie_path, domain_name='trade.shoonya.com')
    return cj._cookies['trade.shoonya.com']['/']['NWC_ID'].value


def validate_token(token, client_id):
    headers = {"jkey": token}
    try:
        url = "https://trade.shoonya.com/NorenWClientWeb/Limits"
        data = {'uid': client_id.upper(), 'actid': client_id.upper()}
        data = f'jData={json.dumps(data)}&jKey={token}'

        response = requests.post(url, data=data, timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        return False

def get_token(client_ids=('fa97273', 'fa222351')):
    CommonToken(client_ids, get_cookie_token, validate_token)


if __name__ == "__main__":
    get_token(['fa97273', 'fa222351'])

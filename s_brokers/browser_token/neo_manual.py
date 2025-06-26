import pyperclip
import jwt
import re
import json

def main():
    uid_map  = {'YL6GN': 'ylcgn', 'S1VDU': 'sivdu'}

    clipboard_content = pyperclip.paste()
    regex = r'"([^"]+)":\s*"([^"]*)"'
    headers = dict(re.findall(regex, clipboard_content))
    authorization, sid = headers["authorization"], headers["sid"]

    uid = jwt.decode(authorization, options={"verify_signature": False})['ucc']
    uid = uid_map[uid]

    json_keys = {
        'authorisation_token': authorization,
        'sid_token': sid,
    }

if __name__ == "__main__":
    main()

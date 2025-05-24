from common.config import get_redis_client, get_browser_profiles
from common.my_logger import logger
from common.utils import TimeCalc
from playwright.sync_api import sync_playwright
import os
import shutil
import tempfile


def get_token(client_id = ('sivdu', 'ylcgn')):
    logger.info(f"Getting tokens for | {client_id}")
    browser_profiles = get_browser_profiles()
    for client in client_id:
        profile = browser_profiles[client]
        temp_folder = get_temp_folder(profile)
        token = extract_token(temp_folder, profile)
        if token['auth'] is not None:
            store_token(client, token['auth'])
            logger.info(f"{client} | ✅ token stored")
        else:
            logger.info(f"{client} | ❌ token not found")


def store_token(client, token):
    r = get_redis_client()
    tc = TimeCalc()
    r.expireat("browser_token", int(tc.next_6am().timestamp()))
    r.hset('browser_token', client, token)


def get_temp_folder(profile):
    user_data_dir = os.path.expanduser("~/Library/Application Support/Microsoft Edge")
    source_profile_path = os.path.join(user_data_dir, profile)
    temp_user_data_folder = tempfile.mkdtemp(prefix="edge_temp_profile_")
    temp_profile_path = os.path.join(temp_user_data_folder, profile)
    shutil.copytree(source_profile_path, temp_profile_path, dirs_exist_ok=True)
    return temp_user_data_folder


def get_browser(p: sync_playwright, temp_folder, profile):
    return p.chromium.launch_persistent_context(
        user_data_dir=temp_folder,
        headless=True,  # Run in headless mode
        channel="msedge",  # Use installed Microsoft Edge
        args=[f"--profile-directory={profile}"]
    )


def extract_token(temp_folder, profile):
    def handle_request(route, request):
        headers = request.headers
        if 'authorization' in headers:
            token['auth'] = headers['authorization']
        route.continue_()

    token = {'auth': None}
    try:
        with sync_playwright() as p:
            browser = get_browser(p, temp_folder, profile)
            page = browser.new_page()

            page.route("**/*", handle_request)
            page.goto("https://ntrade.kotaksecurities.com/")
            page.wait_for_load_state("networkidle", timeout=10000)

            browser.close()
    finally:
        shutil.rmtree(temp_folder, ignore_errors=True)
        return token


if __name__ == '__main__':
    get_token()

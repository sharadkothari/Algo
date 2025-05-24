import os
import shutil
import tempfile
import asyncio
from common.config import get_redis_client, get_browser_profiles
from common.my_logger import logger
from common.utils import TimeCalc
from playwright.async_api import async_playwright
from common.telegram_bot import TelegramBotService as TelegramBot
import time

tbot = TelegramBot(send_only=True)

def get_temp_folder(profile):
    user_data_dir = os.path.expanduser("~/Library/Application Support/Microsoft Edge")
    source_profile_path = os.path.join(user_data_dir, profile)
    temp_user_data_folder = tempfile.mkdtemp(prefix="edge_temp_profile_")
    temp_profile_path = os.path.join(temp_user_data_folder, profile)
    shutil.copytree(source_profile_path, temp_profile_path, dirs_exist_ok=True)
    return temp_user_data_folder


async def get_browser(playwright, temp_folder, profile):
    return await playwright.chromium.launch_persistent_context(
        user_data_dir=temp_folder,
        headless=True,
        channel="msedge",
        args=[f"--profile-directory={profile}"]
    )


async def extract_token(playwright, client, profile):
    token = {'auth': None}
    temp_folder = get_temp_folder(profile)

    async def handle_request(route, request):
        headers = request.headers
        if 'authorization' in headers:
            token['auth'] = headers['authorization']
        await route.continue_()

    try:
        browser = await get_browser(playwright, temp_folder, profile)
        page = await browser.new_page()
        await page.route("**/*", handle_request)
        await page.goto("https://ntrade.kotaksecurities.com/")
        await page.wait_for_load_state("networkidle", timeout=10000)
        await browser.close()
    except Exception as e:
        logger.warning(f"{client} | ❌ error extracting token: {e}")
    finally:
        shutil.rmtree(temp_folder, ignore_errors=True)
    return client, token['auth']


def store_token(client, token):
    r = get_redis_client()
    tc = TimeCalc()
    r.expireat("browser_token", int(tc.next_6am().timestamp()))
    r.hset('browser_token', client, token)


async def get_token_async(client_ids):
    logger.info(f"Getting tokens for | {client_ids}")
    browser_profiles = get_browser_profiles()

    async with async_playwright() as playwright:
        tasks = []
        for client in client_ids:
            profile = browser_profiles.get(client)
            if not profile:
                logger.warning(f"{client} | ❌ profile not found")
                tbot.send(f"{client} |  ❌ error")
                continue
            tasks.append(extract_token(playwright, client, profile))

        results = await asyncio.gather(*tasks)

    for client, token in results:
        if token:
            store_token(client, token)
            logger.info(f"{client} | ✅ token stored")
            tbot.send(f"{client} | ✅ token stored")
        else:
            logger.warning(f"{client} | ❌ token not found")
            tbot.send(f"{client} |  ❌ error")
def get_token(client_ids=('sivdu', 'ylcgn')):
    asyncio.run(get_token_async(client_ids))


if __name__ == '__main__':
    get_token()

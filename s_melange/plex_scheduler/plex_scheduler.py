import time
import subprocess
from common.trading_hours import TradingHours
from common.my_logger import logger

CHECK_INTERVAL = 300  # check every 5 minutes
DOCKER = "/usr/bin/docker"


def is_plex_running():
    result = subprocess.run(
        [DOCKER, "inspect", "-f", "{{.State.Running}}", "plex"],
        capture_output=True,
        text=True
    )
    return result.stdout.strip() == "true"


def stop_plex():
    logger.info("Stopping Plex container...")
    subprocess.run([DOCKER, "stop", "plex"])


def start_plex():
    logger.info("Starting Plex container...")
    subprocess.run([DOCKER, "start", "plex"])


def monitor_plex():
    trading_hours = TradingHours(start_buffer=300)

    while True:
        if trading_hours.is_open():
            if is_plex_running():
                stop_plex()
        else:
            if not is_plex_running():
                start_plex()

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    monitor_plex()

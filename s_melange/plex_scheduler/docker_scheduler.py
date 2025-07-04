import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import subprocess
from datetime import datetime, timedelta
from common.trading_hours import TradingHours
from common.my_logger import logger

DOCKER = "/usr/bin/docker"
SYSTEMCTL = "/usr/bin/systemctl"

def load_config():
    with open("services.yaml", "r") as f:
        return yaml.safe_load(f)["services"]

def execute_start(service_config, service_name):
    if service_config["type"] == "docker":
        container = service_config["container_name"]
        logger.info(f"{datetime.now()}: Starting container {container}")
        subprocess.run([DOCKER, "start", container])
    elif service_config["type"] == "systemd":
        svc = service_config["service_name"]
        logger.info(f"{datetime.now()}: Starting service {svc}")
        subprocess.run([SYSTEMCTL, "start", svc])
    else:
        logger.error(f"Unknown service type for {service_name}")

def execute_stop(service_config, service_name):
    if service_config["type"] == "docker":
        container = service_config["container_name"]
        logger.info(f"{datetime.now()}: Stopping container {container}")
        subprocess.run([DOCKER, "stop", container])
    elif service_config["type"] == "systemd":
        svc = service_config["service_name"]
        logger.info(f"{datetime.now()}: Stopping service {svc}")
        subprocess.run([SYSTEMCTL, "stop", svc])
    else:
        logger.error(f"Unknown service type for {service_name}")

def schedule_services():
    scheduler = BlockingScheduler(timezone="Asia/Kolkata")
    trading_hours = TradingHours(start_buffer=300)

    config = load_config()

    market_open = trading_hours.get_market_open_time()
    market_close = trading_hours.get_market_close_time()

    for svc_name, svc_cfg in config.items():
        for action in ["start", "stop"]:
            sched_time_key = svc_cfg[action]
            if sched_time_key.startswith("market_open"):
                offset = parse_offset(sched_time_key, market_open)
                trigger_time = market_open + offset
            elif sched_time_key.startswith("market_close"):
                offset = parse_offset(sched_time_key, market_close)
                trigger_time = market_close + offset
            else:
                logger.error(f"Invalid schedule time for {svc_name}: {sched_time_key}")
                continue

            scheduler.add_job(
                execute_start if action == "start" else execute_stop,
                trigger=CronTrigger(
                    hour=trigger_time.hour,
                    minute=trigger_time.minute,
                    day_of_week='mon-fri'
                ),
                args=[svc_cfg, svc_name],
                misfire_grace_time=600,
                id=f"{svc_name}_{action}"
            )
            logger.info(f"Scheduled {action} for {svc_name} at {trigger_time.strftime('%H:%M')}")

    logger.info("Market scheduler started.")
    scheduler.start()

def parse_offset(key, base_time):
    """Parses offset like 'market_open_minus_5' into timedelta."""
    if "minus" in key:
        mins = int(key.split("_minus_")[1])
        return timedelta(minutes=-mins)
    elif "plus" in key:
        mins = int(key.split("_plus_")[1])
        return timedelta(minutes=mins)
    else:
        return timedelta(0)

if __name__ == "__main__":
    schedule_services()
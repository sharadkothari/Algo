import time
import subprocess
import yaml
from datetime import datetime
from common.trading_hours import TradingHours
from common.my_logger import logger

CHECK_INTERVAL = 300  # seconds
DOCKER = "/usr/bin/docker"


def load_services():
    with open("docker_services.yaml", 'r') as f:
        config = yaml.safe_load(f)
    services = config.get("services", {})
    for k,v  in services.items():
        buffer = {'start_buffer': 0, "end_buffer": 0}
        buffer_map = {'before_market':'start_buffer', 'after_market':'end_buffer'}
        for i in ('start', 'stop'):
            if e:=v[i]['event']:
                if e in buffer_map:
                    buffer[buffer_map[e]] = v[i]['offset']
        v['trading_hours_obj'] = TradingHours(**buffer)
    return services


def is_container_running(container_name):
    result = subprocess.run(
        [DOCKER, "inspect", "-f", "{{.State.Running}}", container_name],
        capture_output=True,
        text=True
    )
    return result.stdout.strip() == "true"


def start_container(container_name):
    logger.info(f"Starting container: {container_name}")
    subprocess.run([DOCKER, "start", container_name])


def stop_container(container_name):
    logger.info(f"Stopping container: {container_name}")
    subprocess.run([DOCKER, "stop", container_name])

def check_start_stop(service, flag):
    if flag in service and 'event' in service[flag]:
        event = service[flag]['event']
        if event:
            market_is_open = service['trading_hours_obj'].is_open()
            if event == 'before_market':
                return market_is_open
            elif event == 'after_market':
                return not market_is_open
    return False

def monitor_services():
    services = load_services()

    while True:
        for name, config in services.items():
            if config.get("type") != "docker":
                continue  # only docker for now

            container = config.get("container_name", name)
            should_start = check_start_stop(config, 'start')
            should_stop = check_start_stop(config, 'stop')
            running = is_container_running(container)

            if should_stop and running:
                stop_container(container)
            elif should_start and not running:
                start_container(container)

        time.sleep(CHECK_INTERVAL)

def test():
    s = load_services()
    for name, config in s.items():
        should_start = check_start_stop(config, 'start')
        should_stop = check_start_stop(config, 'stop')
        print(name, should_start, should_stop)

if __name__ == "__main__":
    monitor_services()

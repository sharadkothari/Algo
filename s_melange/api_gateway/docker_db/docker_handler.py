import docker
from docker import errors
import redis
from common.config import get_redis_client
from common.my_logger import logger
from ansi2html import Ansi2HTMLConverter

# Connect to Redis and Docker
redis_client = get_redis_client()
# DOCKER_BASE_URL = 'tcp://docker:2375'

class DockerHandler:
    def __init__(self):
        try:
            # self.client = docker.from_env() # for windows
            self.client = docker.DockerClient(base_url='unix:///var/run/docker.sock')
            logger.info('DockerHandler initialized')
        except Exception as e:
            logger.info(f"Error setting docker client: {e}")
            self.client = None

    def get_services(self):
        try:
            services_data = redis_client.hgetall('services')
            services = []
            for name, value in services_data.items():
                container_id, port = value.split(':')
                status = self.get_container_status(container_id)
                services.append({
                    'name': name,
                    'containerId': container_id,
                    'port': port,
                    'status': status,
                })
            return services, 200
        except redis.exceptions.ConnectionError as e:
            logger.info(f"Error connecting to Redis: {e}")
            return {'error': 'Failed to connect to Redis'}, 500
        except docker.errors.APIError as e:  # Use errors.APIError
            logger.info(f"Error connecting to Docker: {e}")
            return {'error': 'Failed to connect to Docker'}, 500
        except Exception as e:
            logger.info(f"Error: {e}")
            return 'error', 500

    def get_container_status(self, container_id):
        if self.client is not None:
            try:
                container = self.client.containers.get(container_id)
                return container.status, 200
            except errors.NotFound:  # Use errors.NotFound
                return 'not_found', 404
            except errors.APIError as e:  # Use errors.APIError
                logger.info(f"Error getting container status: {e}")
                return 'error', 500

    def start_container(self, container_id):
        try:
            container = self.client.containers.get(container_id)
            container.start()
            return {'status': 'started'}, 200
        except errors.NotFound:  # Use errors.NotFound
            return {'error': f'Container {container_id} not found'}, 404
        except errors.APIError as e:  # Use errors.APIError
            logger.info(f"Error starting container {container_id}: {e}")
            return {'error': f'Error starting container: {str(e)}'}, 500
        except Exception as e:
            logger.info(f"Error: {e}")
            return 'error', 500

    def stop_container(self, container_id):
        try:
            container = self.client.containers.get(container_id)
            container.stop()
            return {'status': 'stopped'}, 200
        except errors.NotFound:  # Use errors.NotFound
            return {'error': f'Container {container_id} not found'}, 404
        except errors.APIError as e:  # Use errors.APIError
            logger.info(f"Error stopping container {container_id}: {e}")
            return {'error': f'Error stopping container: {str(e)}'}, 500
        except Exception as e:
            logger.info(f"Error: {e}")
            return 'error', 500

    def restart_container(self, container_id):
        try:
            container = self.client.containers.get(container_id)
            container.restart()
            return {'status': 'restarted'}
        except errors.NotFound:  # Use errors.NotFound
            return {'error': f'Container {container_id} not found'}
        except errors.APIError as e:  # Use errors.APIError
            logger.info(f"Error restarting container {container_id}: {e}")
            return {'error': f'Error restarting container: {str(e)}'}
        except Exception as e:
            logger.info(f"Error: {e}")
            return 'error', 500

    def get_log(self, service_name):
        if value := redis_client.hget("services", service_name):
            container_id = value.split(":")[0]
            try:
                container = self.client.containers.get(container_id)
                logs = container.logs(tail=50)
                conv = Ansi2HTMLConverter(inline=True)
                return {"logs": conv.convert(logs.decode('utf-8'), full=False)}
            except Exception as e:
                return {"error": str(e)}, 500
        else:
            return {"error": f"{service_name} not found"}, 404


To add new service:
1. copy docker and change <service_file>:app
2. Update port in nginx.conf (add new path)
3. Add image information to service level docker_compose.yml (copy and replace name and port)
4. In project level docker_compose.yml add dependencies in nginx
Run:
docker compose up --build -d monorepo_base <new service name>
docker restart nginx
docker image prune -f # if old images needs to be removed
____
To check and close port
1. lsof -i :<port>
2. kill -9 <pid>
___
* till permanent solution is found as docker-compose not connecting
docker update --restart=always redis-stack
docker exec -it redis-stack redis-cli CONFIG SET notify-keyspace-events Khg
docker exec -it redis-stack redis-cli CONFIG SET appendonly no

----
new scheme:

1. cleanup old images
docker compose down --volumes
docker system prune -af

2. Then:

docker compose build monorepo_base
docker compose up -d

A. If requirements.txt is unchanged (just adding a new service)
docker compose up -d <new_service_name>

B. If requirements.txt is changed (but only impacts the new service)
docker compose build monorepo_base
docker compose up -d <new_service_name>

C. If a new library is added for an existing service (edit to requirements.txt)
docker compose build monorepo_base
docker compose up -d <affected_service_name>
or to restart all:
docker compose up -d

d. to remove a service and build again
docker compose rm -f <service_name>
docker compose up -d <service_name>

---
to restart ethernet on t5810
sudo ip link set enp0s25 down && sleep 2 && sudo ip link set enp0s25 up

__
check 1

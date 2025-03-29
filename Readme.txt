
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
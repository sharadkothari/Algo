FROM monorepo_base

COPY microservice2/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY shared /app/shared
COPY microservice2 /app

CMD ["python", "main.py"]